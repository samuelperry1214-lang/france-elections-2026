import requests
from datetime import datetime

RESULTS_API_BASE = "https://www.data.gouv.fr/api/1/datasets/"
RESULTS_DATASET_ROUND1 = "elections-municipales-2026-resultats-du-1er-tour"
RESULTS_DATASET_ROUND2 = "elections-municipales-2026-resultats-du-2eme-tour"

ROUND1_DATE = datetime(2026, 3, 15)
ROUND2_DATE = datetime(2026, 3, 22)


def election_status() -> dict:
    now = datetime.now()
    if now < ROUND1_DATE:
        phase = "pre_election"
        label = "Pre-election — showing polling projections"
    elif now < ROUND2_DATE:
        phase = "round1"
        label = "Round 1 underway / results counting"
    else:
        phase = "round2"
        label = "Round 2 underway / results counting"
    return {"phase": phase, "label": label, "now": now.isoformat()}


def fetch_results() -> dict:
    status = election_status()
    if status["phase"] == "pre_election":
        return {"status": status, "results": {}}
    try:
        r1_url = f"{RESULTS_API_BASE}{RESULTS_DATASET_ROUND1}/"
        resp = requests.get(r1_url, timeout=10)
        if resp.status_code == 200:
            dataset = resp.json()
            resources = dataset.get("resources", [])
            csv_resource = next(
                (r for r in resources if r.get("format", "").lower() == "csv"
                 and "commune" in r.get("title", "").lower()), None
            )
            if csv_resource:
                return {"status": status, "source": "data.gouv.fr",
                        "round1_url": csv_resource["url"], "results": {}}
    except Exception as e:
        print(f"Results fetch error: {e}")
    return {"status": status, "results": {}, "note": "Results not yet published"}
