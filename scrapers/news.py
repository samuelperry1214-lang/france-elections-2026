"""
News scraper for France Elections 2026.

Sources (all free/open-access):
  National FR (translated):  Le Monde, Le Figaro, France Info
  National EN (no paywall):  The Guardian, BBC Europe, France 24 EN,
                              RFI English, The Local France, Euronews,
                              AP News, Reuters
  Paris Playbook:            Full daily editions fetched + translated,
                             paginated back in time

Le Monde and Le Figaro are kept for their headlines/summaries via RSS,
which are freely available even behind a paywall.  We do NOT link to
paywalled full articles — we show the translated headline + RSS abstract.
"""

import feedparser
import requests
from bs4 import BeautifulSoup
from scrapers.translate import translate_to_english

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

# ── Source catalogue ──────────────────────────────────────────────────────────

# French sources (headlines + RSS abstracts freely available; translated)
FR_SOURCES = {
    "Le Monde": {
        "rss_urls": [
            "https://www.lemonde.fr/politique/rss_full.xml",
            "https://www.lemonde.fr/rss/une.xml",
        ],
        "lang": "fr", "color": "#1a1a2e", "logo": "LM",
        "paywall": True,   # show summary only, no click-through promise
    },
    "Le Figaro": {
        "rss_urls": [
            "https://www.lefigaro.fr/rss/figaro_politique.xml",
            "https://www.lefigaro.fr/rss/figaro_actualites.xml",
            "https://www.lefigaro.fr/politique/rss.xml",
            "https://www.lefigaro.fr/rss/figaro_elections.xml",
        ],
        "lang": "fr", "color": "#c0392b", "logo": "LF",
        "paywall": True,
    },
    "France Info": {
        "rss_urls": [
            "https://www.francetvinfo.fr/politique/elections/rss.xml",
            "https://www.francetvinfo.fr/elections/rss.xml",
            "https://www.francetvinfo.fr/politique/rss.xml",
        ],
        "lang": "fr", "color": "#0056a8", "logo": "FI",
        "paywall": False,
    },
}

# English open-access sources — no paywall, no translation needed
EN_SOURCES = {
    "The Guardian": {
        "rss_urls": [
            "https://www.theguardian.com/world/france/rss",
        ],
        "lang": "en", "color": "#052962", "logo": "GU",
        "paywall": False,
    },
    "BBC Europe": {
        "rss_urls": [
            "http://feeds.bbci.co.uk/news/world/europe/rss.xml",
        ],
        "lang": "en", "color": "#bb1919", "logo": "BC",
        "paywall": False,
    },
    "France 24": {
        "rss_urls": [
            "https://www.france24.com/en/tag/french-politics/rss",
            "https://www.france24.com/en/france/rss",
            "https://www.france24.com/en/europe/rss",
        ],
        "lang": "en", "color": "#cc0000", "logo": "F24",
        "paywall": False,
    },
    "The Local France": {
        "rss_urls": [
            "https://feeds.thelocal.com/rss/fr",
            "https://www.thelocal.fr/feed/",
        ],
        "lang": "en", "color": "#c0392b", "logo": "TL",
        "paywall": False,
    },
    "RFI English": {
        "rss_urls": [
            "https://www.rfi.fr/en/france/rss",
            "https://www.rfi.fr/en/rss",
        ],
        "lang": "en", "color": "#0066cc", "logo": "RFI",
        "paywall": False,
    },
    "Euronews": {
        "rss_urls": [
            "https://feeds.feedburner.com/euronewsonline",
            "https://www.euronews.com/rss?level=theme&name=news",
        ],
        "lang": "en", "color": "#00498f", "logo": "EN",
        "paywall": False,
    },
    "AP News": {
        "rss_urls": [
            "https://rsshub.app/apnews/topics/apf-europe",
            "https://feeds.apnews.com/rss/APEurope",
        ],
        "lang": "en", "color": "#333333", "logo": "AP",
        "paywall": False,
    },
}

# City-specific local papers
LOCAL_SOURCES = {
    "paris":       [("Le Parisien",   "https://feeds.leparisien.fr/leparisien/rss",   "#e63946")],
    "marseille":   [("La Provence",   "https://www.laprovence.com/rss.xml",           "#e67e22"),
                    ("Marsactu",      "https://marsactu.fr/feed/",                     "#27ae60")],
    "lyon":        [("Le Progrès",    "https://www.leprogres.fr/rss.xml",             "#8e44ad"),
                    ("Lyon Capitale", "https://www.lyoncapitale.fr/feed/",            "#2980b9")],
    "toulouse":    [("La Dépêche",    "https://www.ladepeche.fr/rss.xml",            "#e74c3c")],
    "nice":        [("Nice-Matin",    "https://www.nicematin.com/rss.xml",            "#00bcd4")],
    "nantes":      [("Ouest France",  "https://www.ouest-france.fr/rss.xml",         "#f39c12")],
    "strasbourg":  [("DNA Alsace",    "https://www.dna.fr/rss.xml",                  "#e74c3c")],
    "bordeaux":    [("Sud Ouest",     "https://www.sudouest.fr/rss.xml",             "#d35400")],
    "montpellier": [("Midi Libre",    "https://www.midilibre.fr/rss.xml",            "#16a085")],
    "lille":       [("La Voix du Nord","https://www.lavoixdunord.fr/rss.xml",        "#2980b9")],
    "rennes":      [("Ouest France",  "https://www.ouest-france.fr/rss.xml",         "#f39c12")],
    "grenoble":    [("Le Dauphiné",   "https://www.ledauphine.com/rss.xml",          "#8e44ad")],
}

ELECTION_KEYWORDS = [
    "municipale", "municipal", "maire", "mairie", "élection", "election",
    "paris", "marseille", "lyon", "toulouse", "nice", "nantes", "strasbourg",
    "bordeaux", "montpellier", "lille", "rennes", "grenoble",
    "grégoire", "gregoire", "dati", "bournazel", "chikirou", "mariani",
    "payan", "allisio", "vassal", "delogu",
    "doucet", "aulas", "moudenc", "briançon", "piquemal",
    "estrosi", "ciotti", "rolland", "barseghian", "trautmann", "hurmic",
    "cazenave", "delafosse", "deslandes", "spillebout", "appéré", "ruffin",
    "carignon", "knafo",
    "rassemblement national", "front national", "rn ", " rn,",
    "parti socialiste", "renaissance", "macron",
    "scrutin", "sondage", "premier tour", "second tour", "vote",
    "french election", "french municipal", "france vote", "france election",
    "france politics", "french politics", "france mayor",
]


def _is_relevant(title: str, summary: str = "") -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in ELECTION_KEYWORDS)


def _clean(html_text: str, max_chars: int = 600) -> str:
    text = BeautifulSoup(html_text or "", "html.parser").get_text(" ", strip=True)
    return text[:max_chars]


def _extract_summary(text: str, max_words: int = 250) -> str:
    """Extract approximately max_words words from the start of a text body."""
    if not text:
        return ""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"


def _tr(text: str, lang: str) -> str:
    """Translate if French, else return as-is."""
    if lang != "fr" or not text:
        return text
    return translate_to_english(text)


# ── Generic RSS scraper ───────────────────────────────────────────────────────

def scrape_rss(source_name: str, rss_urls: list, lang: str, color: str, logo: str,
               paywall: bool = False, max_items: int = 8,
               city_filter: str = None) -> list:
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
        print(f"[rss] No entries: {source_name}")
        return []

    for entry in feed.entries:
        if len(items) >= max_items:
            break

        title   = entry.get("title", "").strip()
        raw_sum = entry.get("summary", entry.get("description", ""))
        summary = _clean(raw_sum, 600)
        link    = entry.get("link", "")
        pub     = entry.get("published", "")

        if city_filter:
            if city_filter.lower() not in (title + summary).lower():
                continue

        if not _is_relevant(title, summary):
            continue

        title_en   = _tr(title, lang)
        summary_en = _tr(summary, lang)

        note = "Headline & abstract — full article may be behind a paywall" if paywall else ""

        items.append({
            "source":          source_name,
            "title":           title_en,
            "title_original":  title,
            "summary":         summary_en,
            "link":            link,
            "published":       pub,
            "color":           color,
            "logo":            logo,
            "city":            city_filter or "national",
            "paywall_note":    note,
            "full_text":       None,
        })

    return items


# ── Paris Playbook ────────────────────────────────────────────────────────────

PLAYBOOK_ROOT  = "https://www.politico.eu"
PLAYBOOK_INDEX = "https://www.politico.eu/newsletter/playbook-paris/"
PLAYBOOK_RSS   = [
    "https://www.politico.eu/feed/?post_type=newsletter&newsletter=playbook-paris",
    "https://www.politico.eu/newsletter/playbook-paris/feed/",
]
# Try paginated archive pages to go back further
PLAYBOOK_PAGES = [
    PLAYBOOK_INDEX,
    PLAYBOOK_INDEX + "page/2/",
    PLAYBOOK_INDEX + "page/3/",
]


def _fetch_playbook_edition(url: str) -> dict | None:
    """
    Fetch a single Playbook edition URL and extract:
      - title (h1)
      - date line
      - full body text (all paragraphs, up to ~4000 chars)
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Title
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""
        if not title and soup.title:
            title = soup.title.string or ""

        # Date
        time_el = soup.find("time")
        date_str = time_el.get_text(strip=True) if time_el else ""
        if not date_str:
            meta_date = soup.find("meta", {"property": "article:published_time"})
            date_str = meta_date["content"][:10] if meta_date else ""

        # Body — try to find the newsletter content container
        article = (
            soup.find("article") or
            soup.find(class_=lambda c: c and any(
                k in c.lower() for k in ["newsletter-body", "article__content",
                                          "article-body", "content-body", "vit-Post"]
            )) or
            soup.find("main")
        )
        paras = article.find_all("p") if article else soup.find_all("p")

        body_parts = []
        for p in paras:
            txt = p.get_text(strip=True)
            if len(txt) > 30:  # skip nav snippets
                body_parts.append(txt)
            if sum(len(x) for x in body_parts) > 4000:
                break
        full_text = "\n\n".join(body_parts)

        if not title and not full_text:
            return None

        return {"title": title, "date": date_str, "full_text": full_text, "url": url}

    except Exception as e:
        print(f"[playbook] Edition fetch error {url}: {e}")
        return None


def _edition_links_from_index(url: str) -> list:
    """Return list of individual edition URLs found on an index/archive page."""
    links = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Edition URLs contain 'playbook-paris' and are not the index itself
            if "playbook-paris" in href and href.rstrip("/") != PLAYBOOK_INDEX.rstrip("/"):
                full = href if href.startswith("http") else PLAYBOOK_ROOT + href
                if full not in links:
                    links.append(full)
    except Exception as e:
        print(f"[playbook] Index scrape error {url}: {e}")
    return links


def scrape_paris_playbook(max_editions: int = 6) -> list:
    items = []
    edition_urls = []

    # 1. Try RSS feeds first — they often carry recent editions
    for rss_url in PLAYBOOK_RSS:
        try:
            feed = feedparser.parse(rss_url, request_headers=HEADERS)
            if feed.entries:
                for entry in feed.entries[:max_editions * 2]:
                    link = entry.get("link", "")
                    if link and link not in edition_urls:
                        edition_urls.append(link)
                print(f"[playbook] RSS gave {len(edition_urls)} links")
                break
        except Exception as e:
            print(f"[playbook] RSS {rss_url}: {e}")

    # 2. Scrape index pages (current + paginated) to go further back
    for page_url in PLAYBOOK_PAGES:
        found = _edition_links_from_index(page_url)
        for u in found:
            if u not in edition_urls:
                edition_urls.append(u)
        print(f"[playbook] Index {page_url} gave {len(found)} links")

    print(f"[playbook] Total edition candidates: {len(edition_urls)}")

    # 3. Fetch and translate each edition
    for url in edition_urls[:max_editions * 2]:
        if len(items) >= max_editions:
            break

        edition = _fetch_playbook_edition(url)
        if not edition or (not edition["title"] and not edition["full_text"]):
            continue

        title_en    = translate_to_english(edition["title"]) if edition["title"] else "(Untitled)"
        # Translate full text in one call (up to 4000 chars)
        full_en     = translate_to_english(edition["full_text"]) if edition["full_text"] else ""
        # Summary = extractive ~250 words from start of translated full text
        summary_en  = _extract_summary(full_en, 250)

        items.append({
            "source":         "Paris Playbook",
            "title":          title_en,
            "title_original": edition["title"],
            "summary":        summary_en,
            "full_text":      full_en,          # full translated newsletter body
            "link":           url,
            "published":      edition.get("date", ""),
            "color":          "#2980b9",
            "logo":           "PP",
            "city":           "national",
            "paywall_note":   "",
            "is_playbook":    True,
        })

    if not items:
        print("[playbook] No editions retrieved")

    return items


# ── City-specific news ────────────────────────────────────────────────────────

def scrape_city_news(city_id: str, keywords: list, max_items: int = 8) -> list:
    items = []

    # Local papers for this city
    for (name, rss_url, color) in LOCAL_SOURCES.get(city_id, []):
        logo = "".join(w[0].upper() for w in name.split()[:2])
        items += scrape_rss(name, [rss_url], "fr", color, logo,
                            max_items=4, city_filter=city_id)

    # English sources filtered to city name
    for src_name, cfg in EN_SOURCES.items():
        items += scrape_rss(src_name, cfg["rss_urls"], cfg["lang"],
                            cfg["color"], cfg["logo"],
                            paywall=cfg["paywall"], max_items=3,
                            city_filter=city_id)

    # Deduplicate
    seen, deduped = set(), []
    for item in items:
        if item["link"] not in seen:
            seen.add(item["link"])
            deduped.append(item)

    return deduped[:max_items * 2]


# ── Main aggregator ───────────────────────────────────────────────────────────

def scrape_all_news() -> list:
    all_items = []

    # French national (translated headlines + abstracts)
    for src_name, cfg in FR_SOURCES.items():
        all_items += scrape_rss(src_name, cfg["rss_urls"], cfg["lang"],
                                cfg["color"], cfg["logo"],
                                paywall=cfg.get("paywall", False))

    # English open-access
    for src_name, cfg in EN_SOURCES.items():
        all_items += scrape_rss(src_name, cfg["rss_urls"], cfg["lang"],
                                cfg["color"], cfg["logo"],
                                paywall=cfg.get("paywall", False))

    # Paris Playbook (full translated editions)
    all_items += scrape_paris_playbook()

    # Deduplicate
    seen, deduped = set(), []
    for item in all_items:
        if item["link"] not in seen:
            seen.add(item["link"])
            deduped.append(item)

    return deduped
