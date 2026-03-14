"""
Scrapes polling data for major French municipal races from Wikipedia
and sondages-france.fr where available.

Returns a dict keyed by city ID, matching the IDs in candidates.json.
"""
import requests
from bs4 import BeautifulSoup

WIKIPEDIA_POLLS = {
    "paris": "https://fr.wikipedia.org/wiki/%C3%89lections_municipales_de_2026_%C3%A0_Paris",
    "marseille": "https://fr.wikipedia.org/wiki/%C3%89lections_municipales_de_2026_%C3%A0_Marseille",
    "lyon": "https://fr.wikipedia.org/wiki/%C3%89lections_municipales_de_2026_%C3%A0_Lyon",
    "toulouse": "https://fr.wikipedia.org/wiki/%C3%89lections_municipales_de_2026_%C3%A0_Toulouse",
    "bordeaux": "https://fr.wikipedia.org/wiki/%C3%89lections_municipales_de_2026_%C3%A0_Bordeaux",
    "nantes": "https://fr.wikipedia.org/wiki/%C3%89lections_municipales_de_2026_%C3%A0_Nantes",
    "lille": "https://fr.wikipedia.org/wiki/%C3%89lections_municipales_de_2026_%C3%A0_Lille",
    "strasbourg": "https://fr.wikipedia.org/wiki/%C3%89lections_municipales_de_2026_%C3%A0_Strasbourg",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ElectionMonitor/1.0)"}


def _parse_poll_table(table) -> list:
    """Parse a Wikipedia polling table into a list of poll dicts."""
    polls = []
    try:
        rows = table.find_all("tr")
        if len(rows) < 2:
            return polls

        headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]

        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if len(cells) < 3:
                continue
            poll = {}
            for i, h in enumerate(headers):
                if i < len(cells):
                    poll[h] = cells[i]
            polls.append(poll)
    except Exception:
        pass
    return polls


def scrape_city_polls(city_id: str, url: str) -> dict:
    """Scrape polls for a single city from its Wikipedia page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return {}

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find tables that look like polling tables
        # Wikipedia polling tables typically have class "wikitable"
        poll_tables = []
        for table in soup.find_all("table", class_="wikitable"):
            text = table.get_text().lower()
            if any(kw in text for kw in ["sondage", "poll", "ifop", "bva", "odoxa", "harris", "opinionway"]):
                poll_tables.append(_parse_poll_table(table))

        return {
            "city": city_id,
            "source": "Wikipedia",
            "url": url,
            "tables": poll_tables[:2]  # Return up to 2 poll tables
        }
    except Exception as e:
        print(f"Poll scrape failed for {city_id}: {e}")
        return {}


def scrape_all_polls() -> dict:
    """Scrape polls for all major cities. Returns dict keyed by city_id."""
    results = {}
    for city_id, url in WIKIPEDIA_POLLS.items():
        data = scrape_city_polls(city_id, url)
        if data:
            results[city_id] = data
    return results
