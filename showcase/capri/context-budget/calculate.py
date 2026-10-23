"""Offline arithmetic for a labelled worked example; no model or network calls."""

from decimal import Decimal
import json
from pathlib import Path
import sys


def calculate(data):
    policies = data["policies"]
    for name, values in policies.items():
        if len(values) != data["calls"] or any(type(v) is not int or v < 0 for v in values):
            raise ValueError(f"Invalid assumed request inputs: {name}")
    totals = {name: sum(values) for name, values in policies.items()}
    if min(totals.values()) <= 0:
        raise ValueError("Comparisons need positive totals")
    scoped = Decimal(totals["scoped_roles"])
    savings = {
        name: float((Decimal(total) - scoped) * 100 / Decimal(total))
        for name, total in totals.items() if name != "scoped_roles"
    }
    cache = data["cache_sensitivity"]
    if cache["growing_history_uncached"] + cache["growing_history_cached"] != totals["growing_history"]:
        raise ValueError("Growing cache assumptions must match total input")
    if cache["scoped_roles_uncached"] + cache["scoped_roles_cached"] != totals["scoped_roles"]:
        raise ValueError("Scoped cache assumptions must match total input")
    sensitivity = []
    for rate in cache["hypothetical_cached_relative_rates"]:
        r = Decimal(rate)
        if not 0 <= r <= 1:
            raise ValueError("Relative input rate must be in [0, 1]")
        growing = Decimal(cache["growing_history_uncached"]) + r * cache["growing_history_cached"]
        scoped_cost = Decimal(cache["scoped_roles_uncached"]) + r * cache["scoped_roles_cached"]
        sensitivity.append({
            "hypothetical_cached_relative_rate": rate,
            "growing_weighted_input_units": float(growing),
            "scoped_weighted_input_units": float(scoped_cost),
            "scoped_reduction_percent": float((growing - scoped_cost) * 100 / growing),
        })
    return {
        "evidence_class": data["evidence_class"],
        "not_measured": ["CAPRI performance", "task quality", "model retention", "actual billing", "latency"],
        "calls_per_policy": data["calls"],
        "total_assumed_input_tokens": totals,
        "peak_assumed_request_tokens": {name: max(values) for name, values in policies.items()},
        "scoped_input_reduction_percent": savings,
        "cache_sensitivity": sensitivity,
        "negative_reduction_means": "Scoped weighted input is higher under those assumptions",
        "display_rule": "Label every chart as a worked example with assumed counts, not a measured CAPRI run",
    }


if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("scenario.json")
    print(json.dumps(calculate(json.loads(source.read_text())), indent=2))
