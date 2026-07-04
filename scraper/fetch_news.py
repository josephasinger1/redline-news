#!/usr/bin/env python3
"""Redline news scraper.

Pulls RSS/Atom feeds from major automotive outlets, keeps only
supercar / sports-car stories, and writes web/data/news.json for the
static app. Stdlib only — no third-party dependencies.
"""

import gzip
import hashlib
import html
import io
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

FEEDS = [
    ("Motor1", "https://www.motor1.com/rss/news/all/"),
    ("Carscoops", "https://www.carscoops.com/feed/"),
    ("Autocar", "https://www.autocar.co.uk/rss"),
    ("Supercar Blondie", "https://supercarblondie.com/feed/"),
    ("The Drive", "https://www.thedrive.com/feed"),
    ("Road & Track", "https://www.roadandtrack.com/rss/all.xml/"),
    ("CarBuzz", "https://carbuzz.com/feed/"),
    ("GTspirit", "https://gtspirit.com/feed/"),
    ("Autoblog", "https://www.autoblog.com/rss.xml"),
    ("Evo", "https://www.evo.co.uk/feed"),
    ("duPont Registry", "https://news.dupontregistry.com/feed/"),
]

# Brand chips shown in the app. Each maps to a word-boundary pattern.
BRANDS = {
    "Ferrari": r"ferrari|\b296\b|\bsf90\b|purosangue|\broma\b|\b812\b|\bf80\b",
    "Lamborghini": r"lamborghini|\blambo\b|huracan|huracán|revuelto|temerario|urus|aventador|countach",
    "Porsche": r"porsche|\b911\b|\b992\b|cayman|boxster|\b718\b|\bgt3\b|\bgt2 rs\b|carrera",
    "McLaren": r"mclaren|\b750s\b|\b765lt\b|artura|\bw1\b(?!\d)|senna|speedtail",
    "Bugatti": r"bugatti|chiron|veyron|tourbillon|mistral",
    "Koenigsegg": r"koenigsegg|jesko|gemera|regera|agera",
    "Pagani": r"pagani|huayra|zonda|utopia",
    "Aston Martin": r"aston martin|vantage|\bdb12\b|\bdbs\b|valkyrie|valhalla|vanquish",
    "Lotus": r"\blotus\b|emira|evija|exige|elise",
    "Maserati": r"maserati|\bmc20\b|granturismo|grecale trofeo",
    "Corvette": r"corvette|\bc8\b|\bz06\b|\bzr1\b|stingray",
    "Rimac": r"\brimac\b|nevera",
    "Alpine": r"\balpine\b.{0,40}\ba110\b|\ba110\b|alpenglow",
    "BMW M": r"\bbmw m[0-9]\b|\bm3\b|\bm4\b|\bm5\b|\bm8\b|\bm2\b(?! ?\.)|bmw.{0,30}\bcsl\b",
    "Mercedes-AMG": r"\bamg\b|mercedes-amg",
    "Audi Sport": r"\baudi\b.{0,40}\b(r8|rs ?[0-9]|quattro concept)\b|\br8\b",
    "Nissan Z/GT-R": r"\bgt-?r\b|nissan z\b|nismo|\b400z\b|fairlady",
    "Toyota GR": r"\bsupra\b|\bgr86\b|\bgr corolla\b|\bgr yaris\b|\blfa\b|lexus lc|lexus rc f|gazoo",
    "Ford": r"\bmustang\b|\bgt350\b|\bgt500\b|ford gt\b|shelby",
    "Dodge": r"\bviper\b|\bhellcat\b|\bdemon\b|challenger|charger daytona",
    "Alfa Romeo": r"alfa romeo|giulia quadrifoglio|\b33 stradale\b|\b4c\b",
    "Honda/Acura": r"\bnsx\b|type r\b|integra type s",
    "Gordon Murray": r"gordon murray|\bt\.?50\b|\bt\.?33\b",
    "Hennessey": r"hennessey|venom f5",
    "Czinger": r"czinger|\b21c\b",
    "Zenvo": r"zenvo|aurora",
    "De Tomaso": r"de tomaso|\bp72\b",
    "Jaguar": r"jaguar.{0,40}\b(f-type|xkss|c-type|d-type)\b|\bf-type\b",
    "Chevrolet Camaro": r"\bcamaro\b",
}

# Generic terms that qualify an article even without a brand match.
GENERAL_TERMS = (
    r"supercar|hypercar|sports ?car|sportscar|track[- ]only|track car|"
    r"grand tourer|\bgt3\b|\bgt4\b|mid-engine|\bv10\b|\bv12\b|\bw16\b|"
    r"nürburgring|nurburgring|goodwood|pebble beach|concours|"
    r"le mans|hypercar class|homologation special|widebody kit|"
    r"million-dollar car|auction record"
)

BRAND_RES = {name: re.compile(pat, re.IGNORECASE) for name, pat in BRANDS.items()}
GENERAL_RE = re.compile(GENERAL_TERMS, re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
WS_RE = re.compile(r"\s+")

MAX_AGE_DAYS = 14
MAX_ARTICLES = 300
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) RedlineNews/1.0"
)


def http_get(url, timeout=25):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
            "Accept-Encoding": "gzip",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip" or data[:2] == b"\x1f\x8b":
            data = gzip.GzipFile(fileobj=io.BytesIO(data)).read()
        return data


def strip_html(text):
    if not text:
        return ""
    text = TAG_RE.sub(" ", html.unescape(text))
    return WS_RE.sub(" ", text).strip()


def parse_date(entry, ns):
    for tag in ("pubDate", "{http://purl.org/dc/elements/1.1/}date"):
        el = entry.find(tag)
        if el is not None and el.text:
            try:
                return parsedate_to_datetime(el.text.strip())
            except (TypeError, ValueError):
                pass
    for tag in ("{%s}published" % ns, "{%s}updated" % ns):
        el = entry.find(tag)
        if el is not None and el.text:
            try:
                return datetime.fromisoformat(el.text.strip().replace("Z", "+00:00"))
            except ValueError:
                pass
    return None


def find_image(entry):
    media_ns = "{http://search.yahoo.com/mrss/}"
    for tag in (media_ns + "content", media_ns + "thumbnail"):
        for el in entry.iter(tag):
            url = el.get("url")
            if url and not el.get("type", "image").startswith(("audio", "video")):
                return url
    for el in entry.findall("enclosure"):
        if el.get("type", "").startswith("image") and el.get("url"):
            return el.get("url")
    content_ns = "{http://purl.org/rss/1.0/modules/content/}encoded"
    for tag in (content_ns, "description"):
        el = entry.find(tag)
        if el is not None and el.text:
            m = IMG_RE.search(el.text)
            if m:
                return m.group(1)
    return None


def parse_feed(source, raw):
    """Yield article dicts from RSS 2.0 or Atom bytes."""
    root = ET.fromstring(raw)
    atom_ns = "http://www.w3.org/2005/Atom"
    items = root.findall(".//item")
    is_atom = False
    if not items:
        items = root.findall(".//{%s}entry" % atom_ns)
        is_atom = True

    for entry in items:
        if is_atom:
            title_el = entry.find("{%s}title" % atom_ns)
            link = None
            for link_el in entry.findall("{%s}link" % atom_ns):
                if link_el.get("rel", "alternate") == "alternate":
                    link = link_el.get("href")
                    break
            summary_el = entry.find("{%s}summary" % atom_ns) or entry.find(
                "{%s}content" % atom_ns
            )
        else:
            title_el = entry.find("title")
            link_el = entry.find("link")
            link = link_el.text.strip() if link_el is not None and link_el.text else None
            summary_el = entry.find("description")

        title = strip_html(title_el.text if title_el is not None else "")
        if not title or not link:
            continue
        summary = strip_html(summary_el.text if summary_el is not None else "")
        published = parse_date(entry, atom_ns)
        yield {
            "title": title,
            "url": link.strip(),
            "source": source,
            "summary": summary[:400],
            "published": published,
            "image": find_image(entry),
        }


def classify(article):
    """Return the list of matched brand chips, or None if off-topic."""
    text = f"{article['title']} {article['summary']}"
    brands = [name for name, rx in BRAND_RES.items() if rx.search(text)]
    if brands:
        return brands[:4]
    if GENERAL_RE.search(text):
        return ["General"]
    return None


def fetch_source(source, url):
    try:
        raw = http_get(url)
        articles = list(parse_feed(source, raw))
        print(f"  [ok]   {source}: {len(articles)} items")
        return articles
    except Exception as exc:  # any single feed failing must not kill the run
        print(f"  [skip] {source}: {type(exc).__name__}: {exc}")
        return []


def main():
    out_path = Path(__file__).resolve().parent.parent / "web" / "data" / "news.json"
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=MAX_AGE_DAYS)

    print(f"Fetching {len(FEEDS)} feeds...")
    all_items = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(fetch_source, name, url) for name, url in FEEDS]
        for fut in as_completed(futures):
            all_items.extend(fut.result())

    seen_urls, seen_titles = set(), set()
    kept = []
    for art in all_items:
        brands = classify(art)
        if not brands:
            continue
        pub = art["published"]
        if pub is not None:
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            if pub < cutoff or pub > now + timedelta(hours=12):
                continue
        url_key = art["url"].split("?")[0].rstrip("/").lower()
        title_key = re.sub(r"\W+", "", art["title"].lower())[:80]
        if url_key in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(url_key)
        seen_titles.add(title_key)
        kept.append(
            {
                "id": hashlib.sha1(url_key.encode()).hexdigest()[:12],
                "title": art["title"],
                "url": art["url"],
                "source": art["source"],
                "summary": art["summary"],
                "image": art["image"],
                "brands": brands,
                "published": (pub or now).isoformat(),
            }
        )

    kept.sort(key=lambda a: a["published"], reverse=True)
    kept = kept[:MAX_ARTICLES]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {"generated_at": now.isoformat(), "count": len(kept), "articles": kept},
            ensure_ascii=False,
            indent=1,
        )
    )
    print(f"Wrote {len(kept)} supercar articles -> {out_path}")
    if not kept:
        print("WARNING: zero articles kept — check feeds/filters", file=sys.stderr)


if __name__ == "__main__":
    main()
