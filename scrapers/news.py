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

import re
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


# ── Playbook parsing helpers ──────────────────────────────────────────────────

# Paragraph that marks the boundary: real content starts AFTER this line
_CONTENT_START_FRAGS = [
    "voir dans le navigateur", "view in browser",
    "envoyez vos infos", "send your tips",
    "abonnez-vous gratuitement",
]

# Paragraphs that signal we've reached the footer — stop here
_FOOTER_START_FRAGS = [
    "à la une :", "a la une :", "dans la presse régionale",
    "dans nos newsletters", "abonnez-vous aux newsletters",
    "subscribe to politico", "aux manettes", "anniversaires",
    "playlist.", "météo.", "dans le jorf",
    "au tableau des médailles", "un grand merci",
    "morning defense", "morning tech", "paris influence",
    "tech matin", "énergie & climat", "energie & climat",
    "et aussi dans", "plus tard.", "pense-bête", "casting.",
]

# Lines to silently skip inside the content block (ads, radio schedule)
_INLINE_SKIP_FRAGS = [
    "un message de ", "a message from ", "présenté par ", "presente par ",
    "sponsored by ", "**un message",
]
_RADIO_RE = re.compile(r'^\d+h\d*[\.:]')   # "7h20.RFI:" or "7h20. RFI:"


def _is_content_start(text: str) -> bool:
    low = text.lower()
    return any(f in low for f in _CONTENT_START_FRAGS)


def _is_footer_start(text: str) -> bool:
    low = text.lower().strip()
    return any(low.startswith(f) or f in low[:80] for f in _FOOTER_START_FRAGS)


def _is_inline_skip(text: str) -> bool:
    low = text.lower()
    return any(f in low for f in _INLINE_SKIP_FRAGS) or bool(_RADIO_RE.match(text))


def _is_boilerplate(text: str) -> bool:
    return _is_inline_skip(text)


# Detects an ALL-CAPS opener like "DANS LA NUIT," or "TEST N°1." at line start
_ALLCAPS_OPENER_RE = re.compile(
    r'^([A-ZÀÂÄÉÈÊËÎÏÔÙÛÜÆŒ°N\s\'\-\,\.«»0-9]{5,}?)[,\.]\s+(.*)',
    re.DOTALL,
)


def _parse_playbook_bullets(translated_text: str, max_words: int = 500) -> str:
    """
    Summarise the full translated Playbook body as clean bullet points.

    Strategy:
    - Strip ALL-CAPS taglines (stylistic openers like "DANS LA NUIT," or
      "TEST N°1.") — the news is in the sentence that follows, not the tag.
    - Distribute the word budget evenly across ALL paragraphs so the whole
      newsletter is represented, not just the opening section.
    - No bold labels — just plain bullets: "• France's first death in Lebanon…"

    If ANTHROPIC_API_KEY is set, delegates to Claude for a proper AI summary.
    """
    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        return _ai_summarise_playbook(translated_text, api_key, max_words)

    # ── Extractive themed fallback ────────────────────────────────────────────
    # Groups paragraphs by political theme, picks best sentence per group.
    # Much better than sequential extraction but not as good as AI.
    return _themed_extractive(translated_text) + (
        "\n\n__AI_KEY_MISSING__"  # flag picked up by scrape_paris_playbook
    )


# Theme keyword sets (checked against translated English text)
_THEMES: list[tuple[str, list[str]]] = [
    ("Macron & government",
     ["macron", "renaissance", "gabriel attal", "premier ministre", "prime minister",
      "élysée", "elysee", "government", "gouvernement", "horizons", "edouard philippe"]),
    ("RN & far right",
     ["rassemblement national", "rn ", "marine le pen", "allisio", "bardella",
      "reconquete", "reconquête", "zemmour", "far right", "extreme right"]),
    ("Left & NFP",
     ["socialiste", "socialist", "parti socialiste", "lfi", "insoumis", "mélenchon",
      "melenchon", "nfp", "front populaire", "eelv", "écologiste", "ecologiste",
      "greens", "ruffin", "glucksmann"]),
    ("Municipal elections",
     ["municipal", "municipale", "mairie", "mayor", "maire", "premier tour",
      "round 1", "first round", "second tour", "runoff", "liste", "candidat"]),
    ("International / defence",
     ["liban", "lebanon", "ukraine", "zelensky", "moyen-orient", "middle east",
      "israel", "iran", "nato", "otan", "défense", "defense", "guerre", "war"]),
]


def _themed_extractive(translated_text: str) -> str:
    """Group paragraphs by political theme and extract one sentence per theme."""
    paras = [p.strip() for p in translated_text.split("\n")
             if p.strip() and len(p.strip()) > 50]

    # Bucket paragraphs into themes
    buckets: dict[str, list[str]] = {t[0]: [] for t in _THEMES}
    buckets["Other"] = []

    for para in paras:
        low = para.lower()
        matched = False
        for theme_name, keywords in _THEMES:
            if any(kw in low for kw in keywords):
                buckets[theme_name].append(para)
                matched = True
                break
        if not matched:
            buckets["Other"].append(para)

    bullets: list[str] = []
    for theme_name, _ in _THEMES:
        group = buckets[theme_name]
        if not group:
            continue
        # Merge all matching paragraphs, strip taglines, take first 2 sentences
        combined = " ".join(group)
        m = _ALLCAPS_OPENER_RE.match(combined)
        body = m.group(2).strip() if (m and m.group(1).strip().isupper()) else combined
        sentences = re.split(r'(?<=[.!?])\s+', body)
        snippet = " ".join(sentences[:2]).strip()
        words = snippet.split()
        if len(words) > 55:
            snippet = " ".join(words[:55]) + "…"
        if snippet:
            bullets.append(f"[{theme_name}] {snippet}")

    return "\n".join(bullets) if bullets else ""


def _ai_summarise_playbook(translated_text: str, api_key: str,
                            max_words: int = 500) -> str:
    """Call Claude Haiku for proper themed abstractive summarisation."""
    from scrapers.usage import budget_ok, record_call
    if not budget_ok():
        print("[playbook] AI summary skipped — £2.50 budget reached")
        return ""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            "You are summarising today's Paris Playbook newsletter (by Politico) "
            "for an English-speaking audience following French politics.\n\n"
            "The full translated text is below. Read ALL of it, then write a "
            "summary grouped by political theme — for example: Macron & government, "
            "RN & far right, The left, Municipal elections, International news. "
            "Only include themes that actually appear in today's newsletter.\n\n"
            "Rules:\n"
            "- Use natural, fluent English sentences — not fragments or translations\n"
            "- Each theme gets 1–3 bullets that synthesise the key developments\n"
            "- Start each theme with a plain header line like 'Macron & government'\n"
            "- Each bullet starts with '• '\n"
            "- No bold, no markdown, no brackets\n"
            f"- Total length: no more than {max_words} words\n\n"
            f"Newsletter text:\n{translated_text[:8000]}"
        )
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        record_call(msg.usage.input_tokens, msg.usage.output_tokens)
        return msg.content[0].text.strip()
    except Exception as e:
        print(f"[playbook] AI summary failed: {e}")
        return ""


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

        # Only collect paragraphs AFTER the "Envoyez vos infos|Voir dans le navigateur"
        # separator, and BEFORE the footer (À la une, Anniversaires, etc.)
        found_start = False
        body_parts  = []
        for p in paras:
            txt = p.get_text(strip=True)
            if not txt:
                continue
            if not found_start:
                if _is_content_start(txt):
                    found_start = True
                continue   # skip header block (author, sponsor, separator line itself)
            if _is_footer_start(txt):
                break      # stop at footer
            if _is_inline_skip(txt) or len(txt) < 35:
                continue   # skip ads, radio schedules, short nav snippets
            body_parts.append(txt)
            if sum(len(x) for x in body_parts) > 10000:
                break
        full_text = "\n".join(body_parts)

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
        # Translate the full cleaned body (post-separator, pre-footer)
        full_en     = translate_to_english(edition["full_text"]) if edition["full_text"] else ""
        # Themed summary — AI if key present, themed-extractive otherwise
        raw_summary = _parse_playbook_bullets(full_en) if full_en else ""
        ai_key_missing = raw_summary.endswith("__AI_KEY_MISSING__")
        summary_en = raw_summary.replace("\n\n__AI_KEY_MISSING__", "").strip()
        if not summary_en:
            summary_en = _extract_summary(full_en, 250)

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
            "ai_key_missing": ai_key_missing,
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
