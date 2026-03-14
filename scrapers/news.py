"""
News scraper for:
  - Politico Paris Playbook  (dives into each day's edition)
  - Le Monde     (RSS)
  - Le Figaro    (RSS — multiple fallback URLs)
  - Local city papers (RSS per city)

All French content is translated to English.
"""
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from scrapers.translate import translate_to_english

# ── Source catalogue ──────────────────────────────────────────
NATIONAL_SOURCES = {
    "Le Monde": {
        "rss_urls": [
            "https://www.lemonde.fr/politique/rss_full.xml",
            "https://www.lemonde.fr/rss/une.xml",
        ],
        "lang": "fr", "color": "#1a1a2e", "logo": "LM",
    },
    "Le Figaro": {
        "rss_urls": [
            "https://www.lefigaro.fr/rss/figaro_politique.xml",
            "https://www.lefigaro.fr/rss/figaro_actualites.xml",
            "https://www.lefigaro.fr/politique/rss.xml",
        ],
        "lang": "fr", "color": "#c0392b", "logo": "LF",
    },
    "France Info": {
        "rss_urls": [
            "https://www.francetvinfo.fr/politique/elections/municipales/rss.xml",
            "https://www.francetvinfo.fr/politique/rss.xml",
        ],
        "lang": "fr", "color": "#0056a8", "logo": "FI",
    },
}

# City-specific local papers with RSS feeds
LOCAL_SOURCES = {
    "paris":      [("Le Parisien",  "https://feeds.leparisien.fr/leparisien/rss", "#e63946")],
    "marseille":  [("La Provence",  "https://www.laprovence.com/rss.xml", "#e67e22"),
                   ("Marsactu",     "https://marsactu.fr/feed/", "#27ae60")],
    "lyon":       [("Le Progrès",   "https://www.leprogres.fr/rss.xml", "#8e44ad"),
                   ("Lyon Capitale","https://www.lyoncapitale.fr/feed/", "#2980b9")],
    "toulouse":   [("La Dépêche",   "https://www.ladepeche.fr/rss.xml", "#e74c3c")],
    "nice":       [("Nice-Matin",   "https://www.nicematin.com/rss.xml", "#00bcd4")],
    "nantes":     [("Ouest France", "https://www.ouest-france.fr/rss.xml", "#f39c12")],
    "strasbourg": [("DNA",          "https://www.dna.fr/rss.xml", "#e74c3c")],
    "bordeaux":   [("Sud Ouest",    "https://www.sudouest.fr/rss.xml", "#d35400")],
    "montpellier":[("Midi Libre",   "https://www.midilibre.fr/rss.xml", "#16a085")],
    "lille":      [("La Voix du Nord","https://www.lavoixdunord.fr/rss.xml", "#2980b9")],
    "rennes":     [("Ouest France", "https://www.ouest-france.fr/rss.xml", "#f39c12")],
    "grenoble":   [("Le Dauphiné",  "https://www.ledauphine.com/rss.xml", "#8e44ad")],
}

ELECTION_KEYWORDS = [
    "municipale", "municipal", "maire", "mairie", "élection", "election",
    "paris", "marseille", "lyon", "toulouse", "nice", "nantes", "strasbourg",
    "bordeaux", "montpellier", "lille", "rennes", "grenoble",
    "hidalgo", "grégoire", "dati", "bournazel", "chikirou", "mariani",
    "payan", "allisio", "vassal", "delogu",
    "doucet", "aulas", "moudenc", "briançon", "piquemal",
    "estrosi", "ciotti", "rolland", "barseghian", "trautmann", "hurmic",
    "cazenave", "delafosse", "deslandes", "spillebout", "appéré", "ruffin", "carignon",
    "rn", "ps", "eelv", "lr", "renaissance", "nfp", "rassemblement",
    "vote", "sondage", "scrutin", "second tour", "premier tour", "macron",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ElectionMonitor/1.0; +https://elections2026.fr)"}


def is_election_relevant(title: str, summary: str = "") -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in ELECTION_KEYWORDS)


def _translate(text: str, lang: str) -> str:
    if lang != "fr" or not text:
        return text
    return translate_to_english(text)


# ── RSS scraper ───────────────────────────────────────────────
def scrape_rss(source_name: str, rss_urls: list, lang: str, color: str, logo: str,
               max_items: int = 8, city_filter: str = None) -> list:
    items = []
    feed = None

    for url in rss_urls:
        try:
            f = feedparser.parse(url, request_headers=HEADERS)
            if f.entries:
                feed = f
                break
        except Exception:
            continue

    if not feed:
        print(f"[news] No RSS entries for {source_name}")
        return []

    for entry in feed.entries:
        if len(items) >= max_items:
            break

        title = entry.get("title", "").strip()
        summary_raw = entry.get("summary", entry.get("description", ""))
        summary = BeautifulSoup(summary_raw, "html.parser").get_text()[:500].strip()
        link = entry.get("link", "")
        published = entry.get("published", "")

        # City filter: if specified, check keywords
        if city_filter:
            city_kw = [city_filter, city_filter.lower()]
            if not any(k in (title + summary).lower() for k in city_kw):
                continue

        if not is_election_relevant(title, summary):
            continue

        title_en   = _translate(title, lang)
        summary_en = _translate(summary, lang)

        items.append({
            "source":          source_name,
            "title":           title_en,
            "title_original":  title,
            "summary":         summary_en,
            "link":            link,
            "published":       published,
            "color":           color,
            "logo":            logo,
            "city":            city_filter or "national",
        })

    return items


# ── Paris Playbook scraper ────────────────────────────────────
PLAYBOOK_INDEX = "https://www.politico.eu/newsletter/playbook-paris/"
PLAYBOOK_RSS_CANDIDATES = [
    "https://www.politico.eu/feed/?post_type=newsletter&newsletter=playbook-paris",
    "https://www.politico.eu/rss/playbook-paris",
    "https://www.politico.eu/feed/newsletter/playbook-paris/",
]


def _fetch_playbook_edition(url: str) -> dict | None:
    """Fetch a single Playbook edition and extract its headline and body."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Title: <h1> or <title>
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else soup.title.string if soup.title else ""

        # Body: paragraphs inside the article / newsletter body
        article = (
            soup.find("article") or
            soup.find(class_=lambda c: c and ("newsletter" in c.lower() or "article" in c.lower() or "content" in c.lower())) or
            soup.find("main")
        )
        if article:
            paragraphs = article.find_all("p")
        else:
            paragraphs = soup.find_all("p")

        # Take first 1200 chars of body
        body = " ".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 40)
        body = body[:1200]

        if not title:
            return None

        return {
            "title": title,
            "summary": body,
            "link": url,
        }
    except Exception as e:
        print(f"[playbook] Edition fetch failed for {url}: {e}")
        return None


def scrape_paris_playbook(max_editions: int = 5) -> list:
    items = []

    # 1. Try RSS feeds first
    for rss_url in PLAYBOOK_RSS_CANDIDATES:
        try:
            feed = feedparser.parse(rss_url, request_headers=HEADERS)
            if feed.entries:
                print(f"[playbook] RSS working: {rss_url}")
                for entry in feed.entries[:max_editions * 2]:
                    if len(items) >= max_editions:
                        break
                    title     = entry.get("title", "").strip()
                    link      = entry.get("link", PLAYBOOK_INDEX)
                    published = entry.get("published", "")
                    # Get full body from the edition page
                    edition = _fetch_playbook_edition(link) if link != PLAYBOOK_INDEX else None
                    if edition:
                        body = edition["summary"]
                    else:
                        body = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text()[:800]

                    if not title:
                        continue

                    title_en   = translate_to_english(title)
                    summary_en = translate_to_english(body) if body else ""

                    items.append({
                        "source":         "Paris Playbook",
                        "title":          title_en,
                        "title_original": title,
                        "summary":        summary_en,
                        "link":           link,
                        "published":      published,
                        "color":          "#2980b9",
                        "logo":           "PP",
                        "city":           "national",
                    })
                if items:
                    return items
        except Exception as e:
            print(f"[playbook] RSS {rss_url} failed: {e}")

    # 2. Fall back: scrape the index page for links to individual editions
    print("[playbook] Falling back to index page scrape")
    try:
        resp = requests.get(PLAYBOOK_INDEX, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find links that look like individual edition pages
        edition_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "playbook-paris" in href and href != PLAYBOOK_INDEX:
                full = href if href.startswith("http") else "https://www.politico.eu" + href
                if full not in edition_links:
                    edition_links.append(full)

        print(f"[playbook] Found {len(edition_links)} edition links on index page")

        for link in edition_links[:max_editions * 2]:
            if len(items) >= max_editions:
                break
            edition = _fetch_playbook_edition(link)
            if not edition:
                continue

            title_en   = translate_to_english(edition["title"])
            summary_en = translate_to_english(edition["summary"]) if edition["summary"] else ""

            items.append({
                "source":         "Paris Playbook",
                "title":          title_en,
                "title_original": edition["title"],
                "summary":        summary_en,
                "link":           link,
                "published":      "",
                "color":          "#2980b9",
                "logo":           "PP",
                "city":           "national",
            })

    except Exception as e:
        print(f"[playbook] Index scrape failed: {e}")

    return items


# ── City-specific news ────────────────────────────────────────
def scrape_city_news(city_id: str, keywords: list, max_items: int = 5) -> list:
    """
    Scrape local papers for a specific city and also filter national sources.
    """
    items = []
    city_name = city_id  # keyword for filtering

    # Local papers
    for (name, rss_url, color) in LOCAL_SOURCES.get(city_id, []):
        logo = "".join(w[0].upper() for w in name.split()[:2])
        items += scrape_rss(
            name, [rss_url], "fr", color, logo,
            max_items=max_items, city_filter=city_name
        )

    # Also pull from national sources filtered to this city
    for src_name, cfg in NATIONAL_SOURCES.items():
        results = scrape_rss(
            src_name, cfg["rss_urls"], cfg["lang"], cfg["color"], cfg["logo"],
            max_items=4, city_filter=city_name
        )
        items += results

    # Deduplicate by link
    seen = set()
    deduped = []
    for item in items:
        if item["link"] not in seen:
            seen.add(item["link"])
            deduped.append(item)

    return deduped[:max_items * 2]


# ── Main aggregator ───────────────────────────────────────────
def scrape_all_news() -> list:
    all_items = []

    # National sources
    for src_name, cfg in NATIONAL_SOURCES.items():
        all_items += scrape_rss(
            src_name, cfg["rss_urls"], cfg["lang"], cfg["color"], cfg["logo"]
        )

    # Paris Playbook (full edition dive)
    all_items += scrape_paris_playbook()

    # Deduplicate
    seen = set()
    deduped = []
    for item in all_items:
        if item["link"] not in seen:
            seen.add(item["link"])
            deduped.append(item)

    return deduped
