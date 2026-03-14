"""
News scraper for:
  - Politico Paris Playbook (https://www.politico.eu/newsletter/playbook-paris/)
  - Le Monde (RSS)
  - Le Figaro (RSS)

All French-language content is translated to English.
"""
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from scrapers.translate import translate_to_english

SOURCES = {
    "Le Monde": {
        "rss": "https://www.lemonde.fr/politique/rss_full.xml",
        "lang": "fr",
        "color": "#1a1a2e",
        "logo": "LM"
    },
    "Le Figaro": {
        "rss": "https://www.lefigaro.fr/rss/figaro_politique.xml",
        "lang": "fr",
        "color": "#c0392b",
        "logo": "LF"
    },
    "Paris Playbook": {
        "url": "https://www.politico.eu/newsletter/playbook-paris/",
        "lang": "fr",
        "color": "#2980b9",
        "logo": "PP"
    }
}

ELECTION_KEYWORDS = [
    "municipale", "municipal", "maire", "mairie", "élection", "election",
    "paris", "marseille", "lyon", "toulouse", "nice", "nantes", "strasbourg",
    "bordeaux", "montpellier", "lille", "rennes", "grenoble",
    "hidalgo", "payan", "doucet", "moudenc", "estrosi", "rolland",
    "barseghian", "hurmic", "delafosse", "aubry", "appéré", "piolle",
    "rn", "ps", "eelv", "lr", "renaissance", "nfp", "rassemblement",
    "vote", "sondage", "poll", "scrutin", "second tour", "premier tour"
]


def is_election_relevant(title: str, summary: str = "") -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in ELECTION_KEYWORDS)


def scrape_rss(source_name: str, config: dict, max_items: int = 8) -> list:
    items = []
    try:
        feed = feedparser.parse(config["rss"])
        for entry in feed.entries[:max_items * 2]:  # Fetch extra, filter down
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            link = entry.get("link", "")
            published = entry.get("published", "")

            if not is_election_relevant(title, summary):
                continue

            # Translate if French
            if config["lang"] == "fr":
                title_en = translate_to_english(title)
                # Keep summary short for translation cost
                summary_clean = BeautifulSoup(summary, "html.parser").get_text()[:400]
                summary_en = translate_to_english(summary_clean)
            else:
                title_en = title
                summary_en = BeautifulSoup(summary, "html.parser").get_text()[:400]

            items.append({
                "source": source_name,
                "title": title_en,
                "title_original": title,
                "summary": summary_en,
                "link": link,
                "published": published,
                "color": config["color"],
                "logo": config["logo"]
            })

            if len(items) >= max_items:
                break

    except Exception as e:
        print(f"RSS scrape failed for {source_name}: {e}")

    return items


def scrape_paris_playbook(max_items: int = 6) -> list:
    items = []
    config = SOURCES["Paris Playbook"]
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ElectionMonitor/1.0)"}
        resp = requests.get(config["url"], headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Politico newsletter page structure: articles in .vit-PostListItem or similar
        # Try multiple selectors to be robust against layout changes
        articles = (
            soup.select("article") or
            soup.select(".vit-PostListItem") or
            soup.select(".story-text") or
            soup.select("h3 a")
        )

        for article in articles[:max_items * 2]:
            # Extract title
            title_tag = article.find("h2") or article.find("h3") or article.find("a")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            if not title:
                continue

            # Extract link
            a_tag = article.find("a", href=True)
            link = a_tag["href"] if a_tag else config["url"]
            if link.startswith("/"):
                link = "https://www.politico.eu" + link

            # Extract summary
            summary_tag = article.find("p")
            summary = summary_tag.get_text(strip=True)[:400] if summary_tag else ""

            if not is_election_relevant(title, summary):
                continue

            # Translate
            title_en = translate_to_english(title)
            summary_en = translate_to_english(summary) if summary else ""

            items.append({
                "source": "Paris Playbook",
                "title": title_en,
                "title_original": title,
                "summary": summary_en,
                "link": link,
                "published": "",
                "color": config["color"],
                "logo": config["logo"]
            })

            if len(items) >= max_items:
                break

        # If no articles found via DOM parsing, try fetching the newsletter RSS if available
        if not items:
            playbook_rss = "https://www.politico.eu/feed/?post_type=newsletter&newsletter=playbook-paris"
            try:
                feed = feedparser.parse(playbook_rss)
                for entry in feed.entries[:max_items]:
                    title = entry.get("title", "")
                    summary = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text()[:400]
                    link = entry.get("link", config["url"])
                    published = entry.get("published", "")
                    title_en = translate_to_english(title)
                    summary_en = translate_to_english(summary) if summary else ""
                    items.append({
                        "source": "Paris Playbook",
                        "title": title_en,
                        "title_original": title,
                        "summary": summary_en,
                        "link": link,
                        "published": published,
                        "color": config["color"],
                        "logo": config["logo"]
                    })
            except Exception as e:
                print(f"Paris Playbook RSS fallback failed: {e}")

    except Exception as e:
        print(f"Paris Playbook scrape failed: {e}")

    return items


def scrape_all_news() -> list:
    all_items = []

    # Scrape Le Monde and Le Figaro in sequence (both RSS)
    all_items += scrape_rss("Le Monde", SOURCES["Le Monde"])
    all_items += scrape_rss("Le Figaro", SOURCES["Le Figaro"])
    all_items += scrape_paris_playbook()

    # Sort by source for now (could add date sorting once dates are normalised)
    return all_items
