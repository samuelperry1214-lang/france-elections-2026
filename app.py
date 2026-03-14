import json
import os
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

CACHE_TTL = 300  # 5 minutes

_cache = {
    "news": {"data": [], "updated": None},
    "polls": {"data": {}, "updated": None},
    "results": {"data": {}, "updated": None},
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
            _cache["news"]["data"] = scrape_all_news()
            _cache["news"]["updated"] = datetime.now()
        except Exception as e:
            app.logger.error(f"News scrape failed: {e}")
    return jsonify(_cache["news"]["data"])


@app.route("/api/polls")
def get_polls():
    if cache_stale("polls"):
        from scrapers.polls import scrape_all_polls
        try:
            _cache["polls"]["data"] = scrape_all_polls()
            _cache["polls"]["updated"] = datetime.now()
        except Exception as e:
            app.logger.error(f"Polls scrape failed: {e}")
    return jsonify(_cache["polls"]["data"])


@app.route("/api/results")
def get_results():
    if cache_stale("results"):
        from scrapers.results import fetch_results
        try:
            _cache["results"]["data"] = fetch_results()
            _cache["results"]["updated"] = datetime.now()
        except Exception as e:
            app.logger.error(f"Results fetch failed: {e}")
    return jsonify(_cache["results"]["data"])


@app.route("/api/status")
def get_status():
    """Returns whether election results are live yet."""
    from scrapers.results import election_status
    return jsonify(election_status())


if __name__ == "__main__":
    app.run(debug=True, port=5000)
