import requests, csv
from datetime import datetime

DATASET_ID = "69b82a7de5d58cc06ad35ce0"
API_URL = f"https://www.data.gouv.fr/api/1/datasets/{DATASET_ID}/"

ROUND1_DATE = datetime(2026, 3, 15)
ROUND2_DATE = datetime(2026, 3, 22)

# Commune codes for tracked cities
COMMUNE_CODES = {
    "75056": "paris",
    "13055": "marseille",
    "69123": "lyon",
    "31555": "toulouse",
    "06088": "nice",
    "44109": "nantes",
    "67482": "strasbourg",
    "33063": "bordeaux",
    "34172": "montpellier",
    "59350": "lille",
    "35238": "rennes",
    "38185": "grenoble",
}

# Map French 2026 municipal election nuance codes to our party keys
NUANCE_TO_PARTY = {
    # Left coalitions & parties
    "LUG":  "PS",         # Union de la Gauche (Grégoire, Payan, Doucet…)
    "LSOC": "PS",         # Socialiste (Trautmann in Strasbourg)
    "LDVG": "PS",         # Diverse Gauche
    "LFI":  "LFI",        # France Insoumise
    "LEXG": "LFI",        # Extrême Gauche (LO, NPA…)
    "LECO": "EELV",       # Écologiste
    "LVEC": "EELV",       # Verts / Écologiste Citoyens (Baly Lille)
    # Centre coalitions
    "LUC":  "Horizons",   # Union du Centre (Bournazel, Gandon…)
    "LDVC": "DVD",        # Diverse Centre (Aulas Lyon, Dessertine Bordeaux…)
    # Right
    "LLR":  "LR",         # Les Républicains
    "LUD":  "LR",         # Union de la Droite (Dati Paris, Estrosi Nice…)
    "LDVD": "LR",         # Diverse Droite (Moudenc Toulouse, Vassal Marseille…)
    # Far right
    "LRN":  "RN",         # Rassemblement National
    "LUXD": "RN",         # Union Extrême Droite (Mariani Paris, Ciotti Nice…)
    "LEXD": "Reconquête", # Extrême Droite (Knafo Paris)
    "LREC": "Reconquête", # Reconquête
    # Other
    "LDIV": "Other",      # Divers
}

# CSV column layout (from actual header analysis)
LIST_START_COL = 18   # first list's "Numéro de panneau" column
COLS_PER_LIST  = 13   # columns per list block
MAX_LISTS      = 13

# Column offsets within each list block
OFF_NUANCE   = 4
OFF_ABBREV   = 5
OFF_LONG     = 6
OFF_PCT_EXP  = 9   # "% Voix/exprimés"
OFF_ELU      = 10  # "Elu"


def election_status() -> dict:
    now = datetime.now()
    if now < ROUND1_DATE:
        phase, label = "pre_election", "Pre-election — showing polling projections"
    elif now < ROUND2_DATE:
        phase, label = "round1", "Round 1 complete — live results"
    else:
        phase, label = "round2", "Round 2 — final results"
    return {"phase": phase, "label": label, "now": now.isoformat()}


def _get_csv_url(title_fragment: str) -> str | None:
    try:
        resp = requests.get(API_URL, timeout=10)
        resources = resp.json().get("resources", [])
        # Filter to matching CSVs, prefer the most recently created one
        matches = [
            r for r in resources
            if r.get("format", "").lower() == "csv"
            and title_fragment.lower() in r.get("title", "").lower()
        ]
        if not matches:
            return None
        matches.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return matches[0]["url"]
    except Exception:
        return None


def _pct(val: str) -> float:
    try:
        return round(float(val.replace(",", ".").replace("%", "").strip()), 1)
    except (ValueError, AttributeError):
        return 0.0


def _parse_communes_csv(url: str) -> dict:
    results = {}
    try:
        resp = requests.get(url, timeout=30, stream=True)
        resp.encoding = "utf-8"
        reader = csv.reader(resp.iter_lines(decode_unicode=True),
                            delimiter=";", quotechar='"')
        next(reader)  # skip header

        for row in reader:
            if len(row) < LIST_START_COL:
                continue
            commune_code = row[2].strip().strip('"')
            if commune_code not in COMMUNE_CODES:
                continue

            city_id   = COMMUNE_CODES[commune_code]
            inscrits  = int(row[4]) if str(row[4]).isdigit() else 0
            votants   = int(row[5]) if str(row[5]).isdigit() else 0
            exprimes  = int(row[9]) if str(row[9]).isdigit() else 0
            turnout   = _pct(row[6])

            lists = []
            for n in range(MAX_LISTS):
                base = LIST_START_COL + n * COLS_PER_LIST
                if base + OFF_ELU >= len(row):
                    break
                nuance = row[base + OFF_NUANCE].strip()
                if not nuance:
                    continue
                label      = row[base + OFF_ABBREV].strip()
                full_label = row[base + OFF_LONG].strip()
                pct        = _pct(row[base + OFF_PCT_EXP])
                elu        = row[base + OFF_ELU].strip() == "1"
                party      = NUANCE_TO_PARTY.get(nuance, "Other")
                lists.append({
                    "nuance":     nuance,
                    "label":      label or full_label,
                    "full_label": full_label or label,
                    "party":      party,
                    "pct":        pct,
                    "elected":    elu,
                })

            lists.sort(key=lambda x: x["pct"], reverse=True)
            winner = next((l for l in lists if l["elected"]), None)

            results[city_id] = {
                "commune":       row[3].strip(),
                "inscrits":      inscrits,
                "votants":       votants,
                "turnout_pct":   turnout,
                "exprimes":      exprimes,
                "lists":         lists,
                "winner":        winner,
                "round2_needed": winner is None and len(lists) > 1,
            }
    except Exception as e:
        print(f"Results CSV parse error: {e}")
    return results


# Known fallback URLs by round
_FALLBACK_R1_CSV = (
    "https://static.data.gouv.fr/resources/"
    "elections-municipales-2026-resultats-du-premier-tour/"
    "20260316-160646/municipales-2026-resultats-communes-2026-03-16.csv"
)


def fetch_results() -> dict:
    status = election_status()
    if status["phase"] == "pre_election":
        return {"status": status, "results": {}}

    # For round 2, try the most recent communes CSV from the dataset (government
    # will add a new resource tonight). Fall back to round 1 only if needed.
    csv_url = _get_csv_url("résultats - communes")
    if not csv_url:
        csv_url = _FALLBACK_R1_CSV
    results = _parse_communes_csv(csv_url)
    return {
        "status": status,
        "source": "data.gouv.fr — Ministère de l'Intérieur",
        "results": results,
    }
