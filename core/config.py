import json
import re
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


CLASS_WORD_RE = re.compile(
    r"\s+(inhibitors?|antagonists?|agonists?|blockers?|modulators?|degraders?|"
    r"antibod(?:y|ies)|binders?)\s*$", re.I)


def looks_like_class(text) -> bool:
    return bool(CLASS_WORD_RE.search((text or "").strip()))


def target_symbol(text) -> str:
    """'BTK inhibitor' -> 'BTK'."""
    return CLASS_WORD_RE.sub("", (text or "").strip()).strip()


def slug(text) -> str:
    """File-name friendly form: 'BTK inhibitor' -> 'btk_inhibitor'."""
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")