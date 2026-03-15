import json
import os
from datetime import datetime
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

CACHE_TTL = 300  # 5 minutes

_cache = {
    "news":       {"data": [],  "updated": None},
    "city_news":  {"data": {},  "updated": None},
    "polls":      {"data": {},  "updated": None},
    "results":    {"data": {},  "updated": None},
}


def cache_stale(key):
    updated = _cache[key]["updated"]
    if updated is None:
        return True
    return (datetime.now() - updated).total_seconds() > CACHE_TTL


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/candidates")
def get_candidates():
    path = os.path.join(os.path.dirname(__file__), "data", "candidates.json")
    with open(path, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))


@app.route("/api/news")
def get_news():
    if cache_stale("news"):
        from scrapers.news import scrape_all_news
        try:
            _cache["news"]["data"]    = scrape_all_news()
            _cache["news"]["updated"] = datetime.now()
        except Exception as e:
            app.logger.error(f"News scrape failed: {e}")
    return jsonify(_cache["news"]["data"])


@app.route("/api/news/<city_id>")
def get_city_news(city_id: str):
    """Returns news articles relevant to a specific city."""
    city_cache = _cache["city_news"]["data"]
    city_updated = _cache["city_news"].get("updated_cities", {})

    stale = city_updated.get(city_id) is None or \
            (datetime.now() - city_updated.get(city_id, datetime.min)).total_seconds() > CACHE_TTL

    if stale:
        from scrapers.news import scrape_city_news
        # Load keywords from candidates.json
        try:
            cpath = os.path.join(os.path.dirname(__file__), "data", "candidates.json")
            with open(cpath, "r", encoding="utf-8") as f:
                cdata = json.load(f)
            race = next((r for r in cdata["major_races"] if r["id"] == city_id), None)
            keywords = race["analysis_keywords"] if race else [city_id]
        except Exception:
            keywords = [city_id]

        try:
            items = scrape_city_news(city_id, keywords)
            city_cache[city_id] = items
            _cache["city_news"]["data"] = city_cache
            if "updated_cities" not in _cache["city_news"]:
                _cache["city_news"]["updated_cities"] = {}
            _cache["city_news"]["updated_cities"][city_id] = datetime.now()
        except Exception as e:
            app.logger.error(f"City news scrape failed for {city_id}: {e}")
            city_cache[city_id] = []

    return jsonify(city_cache.get(city_id, []))


@app.route("/api/polls")
def get_polls():
    if cache_stale("polls"):
        from scrapers.polls import scrape_all_polls
        try:
            _cache["polls"]["data"]    = scrape_all_polls()
            _cache["polls"]["updated"] = datetime.now()
        except Exception as e:
            app.logger.error(f"Polls scrape failed: {e}")
    return jsonify(_cache["polls"]["data"])


@app.route("/api/results")
def get_results():
    if cache_stale("results"):
        from scrapers.results import fetch_results
        try:
            _cache["results"]["data"]    = fetch_results()
            _cache["results"]["updated"] = datetime.now()
        except Exception as e:
            app.logger.error(f"Results fetch failed: {e}")
    return jsonify(_cache["results"]["data"])


@app.route("/api/status")
def get_status():
    from scrapers.results import election_status
    return jsonify(election_status())


@app.route("/api/news/digest")
def get_news_digest():
    # Use cached news; regenerate digest if news has refreshed
    from scrapers.news import build_news_digest
    items = _cache["news"]["data"]
    if not items:
        return jsonify({"digest": ""})
    digest = build_news_digest(items)
    return jsonify({"digest": digest})


@app.route("/api/usage")
def get_usage():
    from scrapers.usage import get_usage
    return jsonify(get_usage())


@app.route("/api/debug")
def get_debug():
    import os
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY", ""))
    has_deepl     = bool(os.environ.get("DEEPL_API_KEY", ""))
    vercel        = os.environ.get("VERCEL", "")
    from scrapers.usage import _USAGE_PATH, budget_ok
    try:
        ok = budget_ok()
    except Exception as e:
        ok = f"error: {e}"
    return jsonify({
        "anthropic_key_set": has_anthropic,
        "deepl_key_set":     has_deepl,
        "vercel_env":        vercel,
        "usage_path":        _USAGE_PATH,
        "budget_ok":         ok,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
