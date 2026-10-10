import json
from pathlib import Path

DRUG_NAMES: set = set()

PRICE_IN_PER_M = 0.40
PRICE_OUT_PER_M = 1.25


def fetched_target(results_dir):
    try:
        with open(Path(results_dir) / "evidence_raw.json", encoding="utf-8") as f:
            inp = json.load(f).get("input", {})
    except (OSError, ValueError, AttributeError):
        return None, None
    return (inp.get("mechanism") or None), (inp.get("indication") or None)


def same_name(a, b) -> bool:
    return (a or "").strip().lower() == (b or "").strip().lower()