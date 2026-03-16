"""
Round 2 projection engine for the 2026 French municipal elections.

Uses Claude Haiku to analyse Round 1 results + French tactical voting norms
and output structured per-city Round 2 projections.  Results are cached for
12 hours so we don't burn API credits on every page load.
"""

import json, os, re
from datetime import datetime

_HERE = os.path.dirname(__file__)
CACHE_PATH = os.path.join(_HERE, "..", "data", "round2_cache.json")
CACHE_HOURS = 12

FRENCH_CONTEXT = """
French municipal election Round 2 rules and tactical-voting norms (2026):

RULES
- Any list that scored ≥5% of expressed votes in Round 1 may enter Round 2.
- Lists with ≥10% may merge ("fusion") with another qualifying list before Round 2.
- A list wins outright if it clears 50% + 1 of expressed votes (and ≥25% of registered voters).
- The list with the most votes wins even without an absolute majority.

TACTICAL VOTING PATTERNS
- RN (and allied LUXD lists) face a broad "republican front": when RN leads or threatens to win,
  left, green and centrist voters typically consolidate behind the strongest non-RN candidate.
- LFI lists often face the same cordon sanitaire from PS, EELV and centre-right voters.
- When RN is NOT a threat, the left bloc (LFI + LUG) tends to fragment — PS and LFI may
  compete into Round 2 rather than unite.
- Horizons/Renaissance (LUC) voters split roughly: 60% to the centre-right LR candidate,
  30% to PS/left, 10% abstain — when their list withdraws.
- Reconquête (LEXD/LREC) voter transfer: ~55% to RN/LUXD, ~30% to LR/LUD, 15% abstain.
- LR (LUD/LDVD) voter transfer if their list withdraws: ~50% to LUC/centre, ~30% to RN, 20% left.
- DVG/LDVG minor lists: transfers go ~70% to LUG/PS, ~20% abstain, 10% elsewhere.
- LEXG (far-left, LO, NPA): ~60% abstain or spoil in Round 2, ~30% vote LFI, 10% LUG/PS.
"""


def get_round2_projections(city_results: dict, candidates_data: dict) -> dict:
    """Return cached projections if fresh, otherwise generate new ones via Claude."""
    cache = _load_cache()
    if cache:
        age_h = (datetime.now() - datetime.fromisoformat(cache["generated_at"])).total_seconds() / 3600
        if age_h < CACHE_HOURS:
            return cache.get("projections", {})

    projections = _generate(city_results, candidates_data)
    if projections:
        _save_cache(projections)
    return projections


def _load_cache() -> dict:
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(projections: dict):
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"generated_at": datetime.now().isoformat(),
                       "projections": projections}, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"round2 cache write error: {e}")


def _build_city_block(city_id: str, result: dict, race: dict) -> str:
    qualifiers = [l for l in result.get("lists", []) if l["pct"] >= 5.0]
    if not qualifiers:
        return ""
    lines = [f"### {result.get('commune', city_id)} (id: {city_id}) — Turnout {result.get('turnout_pct')}%"]
    lines.append("Round 1 qualifying lists (≥5%):")
    for l in qualifiers:
        label = l.get("full_label") or l.get("label", "?")
        lines.append(f"  {l['pct']}% — nuance:{l['nuance']} — \"{label}\"")
    ctx = (race.get("context") or "")[:400]
    if ctx:
        lines.append(f"Political context: {ctx}")
    return "\n".join(lines)


def _generate(city_results: dict, candidates_data: dict) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {}

    from scrapers.usage import budget_ok, record_call
    if not budget_ok():
        return {}

    races_by_id = {r["id"]: r for r in candidates_data.get("major_races", [])}

    city_blocks = []
    for city_id, result in city_results.items():
        block = _build_city_block(city_id, result, races_by_id.get(city_id, {}))
        if block:
            city_blocks.append(block)

    if not city_blocks:
        return {}

    city_ids = list(city_results.keys())
    prompt = f"""\
You are a French political analyst producing Round 2 projections for the 2026 municipal elections (Round 2 date: 22 March 2026).

{FRENCH_CONTEXT}

Using the Round 1 results below, project the most likely Round 2 outcome for each city.
Apply realistic tactical-voting transfers: account for which lists may merge or withdraw,
which candidate benefits most from transfer votes, and whether a republican front forms against RN/LFI.

OUTPUT: Return ONLY valid JSON — no markdown, no explanation outside the JSON.
Use these exact city IDs as keys: {json.dumps(city_ids)}

Schema per city:
{{
  "round1_summary": "2-3 sentence plain-English summary of what actually happened in Round 1 — who led, surprises vs polls, how many qualify for Round 2",
  "projected_winner": "short name of winning list/candidate",
  "winner_party": "one of: PS RN LFI EELV LR Horizons DVD Reconquête Other",
  "winner_pct_range": "e.g. 51-56%",
  "runner_up": "short name",
  "runner_up_party": "party key",
  "runner_up_pct_range": "e.g. 44-49%",
  "qualifiers_in_r2": ["list1 short name", "list2 short name"],
  "key_dynamic": "2-3 sentence plain-English analysis of the decisive tactical dynamic for Round 2"
}}

ROUND 1 DATA:
{chr(10).join(city_blocks)}
"""

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        record_call(msg.usage.input_tokens, msg.usage.output_tokens)

        text = msg.content[0].text.strip()
        # Strip markdown code fences if present
        text = re.sub(r"^```[a-z]*\n?", "", text).rstrip("`").strip()
        return json.loads(text)
    except Exception as e:
        print(f"Round 2 generation error: {e}")
        return {}
