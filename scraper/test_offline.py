#!/usr/bin/env python3
"""Offline smoke test for fetch_news parsing + filtering (no network)."""

import fetch_news as fn

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel><title>Test</title>
<item>
  <title>Ferrari F80 Sets New Nurburgring Record</title>
  <link>https://example.com/ferrari-f80</link>
  <pubDate>Fri, 03 Jul 2026 10:00:00 +0000</pubDate>
  <description>&lt;p&gt;The hybrid V12 hypercar laps the Ring in record time.&lt;/p&gt;</description>
  <media:content url="https://example.com/f80.jpg" type="image/jpeg"/>
</item>
<item>
  <title>Best Family Minivans of 2026</title>
  <link>https://example.com/minivans</link>
  <pubDate>Fri, 03 Jul 2026 09:00:00 +0000</pubDate>
  <description>Practical people movers compared.</description>
</item>
<item>
  <title>Porsche 911 GT3 RS Gets Manthey Kit</title>
  <link>https://example.com/gt3rs?utm_source=rss</link>
  <pubDate>Thu, 02 Jul 2026 12:00:00 +0000</pubDate>
  <description>More downforce for the track weapon. &lt;img src="https://example.com/gt3.jpg"/&gt;</description>
</item>
<item>
  <title>Porsche 911 GT3 RS Gets Manthey Kit</title>
  <link>https://example.com/gt3rs-duplicate</link>
  <pubDate>Thu, 02 Jul 2026 12:05:00 +0000</pubDate>
  <description>Duplicate title should be deduped.</description>
</item>
</channel></rss>"""

ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Atom Test</title>
<entry>
  <title>Lamborghini Temerario Spotted Testing</title>
  <link rel="alternate" href="https://example.com/temerario"/>
  <published>2026-07-02T08:00:00Z</published>
  <summary>The Huracan successor hits the road.</summary>
</entry>
</feed>"""


def run():
    rss_items = list(fn.parse_feed("TestRSS", RSS.encode()))
    assert len(rss_items) == 4, rss_items
    assert rss_items[0]["image"] == "https://example.com/f80.jpg"
    assert rss_items[2]["image"] == "https://example.com/gt3.jpg", "img fallback from description"
    assert rss_items[0]["published"] is not None

    atom_items = list(fn.parse_feed("TestAtom", ATOM.encode()))
    assert len(atom_items) == 1 and atom_items[0]["url"] == "https://example.com/temerario"

    assert fn.classify(rss_items[0]) == ["Ferrari"]
    assert fn.classify(rss_items[1]) is None, "minivans must be filtered out"
    assert "Porsche" in fn.classify(rss_items[2])
    assert fn.classify(atom_items[0]) == ["Lamborghini"]

    generic = {"title": "This $3M hypercar sold at auction", "summary": ""}
    assert fn.classify(generic) == ["General"]

    print("All offline tests passed.")


if __name__ == "__main__":
    run()
