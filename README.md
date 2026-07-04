# Redline — Daily Supercar News

A zero-server, zero-cost news app for supercars and sports cars. A scraper
pulls RSS feeds from major automotive outlets three times a day, keeps only
supercar/sports-car stories, and publishes this mobile-first web app to
GitHub Pages — anyone can open it, no account or install required.

**Live app:** https://josephasinger1.github.io/redline-news/

📱 **On iPhone:** open the link in Safari → Share → **Add to Home Screen**
for a fullscreen, native-feeling app with its own icon.

## How it works

```
GitHub Actions (cron, 3×/day)
  └─ scraper/fetch_news.py     ← fetches ~11 RSS feeds, Python stdlib only
       └─ web/data/news.json   ← filtered, deduped, sorted articles
            └─ deployed with the static app to GitHub Pages
```

- **`scraper/fetch_news.py`** — fetches the feeds in parallel, filters by
  brand/keyword patterns (Ferrari, Lamborghini, Porsche GT cars, hypercar,
  Nürburgring, …), strips HTML, extracts a lead image, dedupes by URL and
  title, keeps the last 14 days (max 300 stories). No dependencies.
- **`web/`** — static app: vanilla JS, dark theme, brand filter chips,
  search, day-grouped scrollable cards. Installable as a PWA.
- **`.github/workflows/deploy.yml`** — scrapes and redeploys on a schedule
  (05:15 / 13:15 / 21:15 UTC), on every push to `main`, or manually via
  *Run workflow*.

## Local development

```bash
python3 scraper/fetch_news.py        # needs open internet
python3 scraper/test_offline.py      # parser/filter tests, no network
python3 scraper/make_icons.py        # regenerate app icons
cd web && python3 -m http.server     # then open http://localhost:8000
```

## Tuning what shows up

Edit `BRANDS` (adds a filter chip per brand) and `GENERAL_TERMS` in
`scraper/fetch_news.py`. Add or remove sources in `FEEDS` — a feed that
goes down is skipped gracefully.
