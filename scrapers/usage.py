"""
API usage tracker for Claude Haiku calls.

Persists token counts and estimated cost to data/api_usage.json so the
budget survives server restarts.  The £2.50 cap is enforced before each
call; if exceeded the call is skipped and callers fall back to extractive.
"""

import json
import os
import threading
from datetime import datetime

# ── Pricing (claude-haiku-4-5-20251001, USD per token) ────────────────────────
# Haiku 4.5: $1.00 / MTok input,  $5.00 / MTok output  (conservative estimate)
INPUT_PRICE_PER_TOKEN  = 1.00 / 1_000_000
OUTPUT_PRICE_PER_TOKEN = 5.00 / 1_000_000

GBP_BUDGET   = 2.50
USD_PER_GBP  = 1.27          # fixed conversion rate
USD_BUDGET   = GBP_BUDGET * USD_PER_GBP   # ≈ $3.175

_USAGE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "api_usage.json"
)
_lock = threading.Lock()


def _read() -> dict:
    try:
        with open(_USAGE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "total_input_tokens":  0,
            "total_output_tokens": 0,
            "total_cost_usd":      0.0,
            "calls":               0,
            "last_call":           None,
        }


def _write(data: dict) -> None:
    os.makedirs(os.path.dirname(_USAGE_PATH), exist_ok=True)
    with open(_USAGE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_usage() -> dict:
    """Return current usage stats plus budget metadata."""
    data = _read()
    cost_gbp   = data["total_cost_usd"] / USD_PER_GBP
    remaining  = max(0.0, GBP_BUDGET - cost_gbp)
    pct_used   = min(100, round(cost_gbp / GBP_BUDGET * 100, 1))
    return {
        **data,
        "cost_gbp":       round(cost_gbp, 4),
        "budget_gbp":     GBP_BUDGET,
        "remaining_gbp":  round(remaining, 4),
        "pct_used":       pct_used,
        "budget_exceeded": cost_gbp >= GBP_BUDGET,
    }


def budget_ok() -> bool:
    """Return True if we are still within the £2.50 budget."""
    data = _read()
    spent_gbp = data["total_cost_usd"] / USD_PER_GBP
    return spent_gbp < GBP_BUDGET


def record_call(input_tokens: int, output_tokens: int) -> None:
    """Add one API call's tokens to the persistent ledger."""
    cost = input_tokens * INPUT_PRICE_PER_TOKEN + output_tokens * OUTPUT_PRICE_PER_TOKEN
    with _lock:
        data = _read()
        data["total_input_tokens"]  += input_tokens
        data["total_output_tokens"] += output_tokens
        data["total_cost_usd"]      += cost
        data["calls"]               += 1
        data["last_call"]            = datetime.now().isoformat(timespec="seconds")
        _write(data)
    print(f"[usage] call recorded: {input_tokens}in/{output_tokens}out "
          f"≈ ${cost:.4f}  |  total: ${data['total_cost_usd']:.4f}")
