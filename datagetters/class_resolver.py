"""
class_resolver.py — turns a drug CLASS ("BTK inhibitor") into the drugs that belong to it
and are being developed in the given indication.

Nothing here is hardcoded for one class. The steps are:
  1. "BTK inhibitor" -> target symbol "BTK" (the class word is stripped) -> Open Targets target id.
  2. Candidates from two independent sources:
       a) Open Targets: drugs that act on this target;
       b) ClinicalTrials.gov: interventions of trials in the indication that mention the
          target / the class text.
  3. Every candidate is checked against Open Targets: its mechanism of action must really
     point at the target (so comparators such as teriflunomide are rejected).
  4. A member needs at least one registered trial in the indication. Members are ranked by
     the highest trial phase, then by the number of trials.

Result: results/class_members.json (can be edited by hand; main.py also accepts
--drugs "a,b,c" to skip this step).

Run:  python datagetters/class_resolver.py "BTK inhibitor" "multiple sclerosis" [--max 5]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import looks_like_class, slug, target_symbol  # noqa: E402,F401
from getters.base import get_json
from getters.competitors import SKIP_RE, drug_key
from getters.opentargets import OTError, gql, search

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"
OUTPUT_PATH = RESULTS_DIR / "class_members.json"

CT_URL = "https://clinicaltrials.gov/api/v2/studies"
CT_PAGES = 3
CANDIDATE_LIMIT = 60
DRUG_TYPES = {"DRUG", "BIOLOGICAL", "COMBINATION_PRODUCT"}
PHASE_RANK = {"EARLY_PHASE1": 0.5, "PHASE1": 1, "PHASE2": 2, "PHASE3": 3, "PHASE4": 4}

# ------------------------------------------------------------ Open Targets

def find_target(symbol: str) -> dict | None:
    hits = [h for h in search(symbol, ["target"]) if (h.get("entity") or "").lower() == "target"]
    if not hits:
        return None
    for h in hits:
        if (h.get("name") or "").upper() == symbol.upper():
            return h
    return hits[0]


# The Open Targets schema changes between releases, so several query shapes are tried.
TARGET_DRUG_QUERIES = [
    ("""query($id: String!) { target(ensemblId: $id) { drugAndClinicalCandidates {
          rows { drug { id name } } } } }""",
     lambda t: [r["drug"] for r in ((t.get("drugAndClinicalCandidates") or {}).get("rows") or [])
                if r.get("drug")]),
    ("""query($id: String!) { target(ensemblId: $id) { knownDrugs(size: 500) {
          rows { drugId prefName } } } }""",
     lambda t: [{"id": r["drugId"], "name": r.get("prefName")}
                for r in ((t.get("knownDrugs") or {}).get("rows") or []) if r.get("drugId")]),
]


def drugs_of_target(ensembl_id: str, notes: list) -> list[dict]:
    for query, extract in TARGET_DRUG_QUERIES:
        try:
            data = gql(query, {"id": ensembl_id})
        except OTError as e:
            notes.append(f"Open Targets query variant failed: {str(e)[:120]}")
            continue
        found = extract(data.get("target") or {})
        if found:
            seen, out = set(), []
            for d in found:
                if d["id"] not in seen:
                    seen.add(d["id"])
                    out.append({"chembl_id": d["id"], "name": d.get("name")})
            return out
    return []


DRUG_MECH_Q = """query($id: String!) { drug(chemblId: $id) { id name
  mechanismsOfAction { rows { targets { approvedSymbol } } } } }"""


def verified_drug(chembl_id: str, symbol: str) -> dict | None:
    """Drug from Open Targets, only if one of its mechanisms acts on the target."""
    try:
        drug = gql(DRUG_MECH_Q, {"id": chembl_id}).get("drug")
    except OTError:
        return None
    if not drug:
        return None
    rows = (drug.get("mechanismsOfAction") or {}).get("rows") or []
    symbols = {t.get("approvedSymbol", "").upper() for r in rows for t in r.get("targets") or []}
    if symbol.upper() not in symbols:
        return None
    return {"chembl_id": drug["id"], "name": drug.get("name")}


def resolve_name(name: str, symbol: str) -> dict | None:
    """Registry name or code ('SAR442168') -> verified Open Targets drug, or None."""
    try:
        hits = [h for h in search(name, ["drug"]) if (h.get("entity") or "").lower() == "drug"]
    except OTError:
        return None
    return verified_drug(hits[0]["id"], symbol) if hits else None


# ------------------------------------------------------------ ClinicalTrials.gov

def ct_studies(indication: str, intr: str | None = None, pages: int = CT_PAGES,
               phase3: bool = False) -> list[dict]:
    params = {"pageSize": 100, "format": "json", "query.cond": indication}
    if intr:
        params["query.intr"] = intr
    if phase3:
        params["filter.advanced"] = "AREA[Phase]PHASE3"
    studies = []
    for _ in range(pages):
        data = get_json(CT_URL, params)
        studies += data.get("studies", [])
        token = data.get("nextPageToken")
        if not token:
            break
        params["pageToken"] = token
    return studies


def parse_study(st: dict) -> tuple[str, list[str], float]:
    proto = st.get("protocolSection", {})
    nct = proto.get("identificationModule", {}).get("nctId", "")
    names = [i.get("name", "") for i in proto.get("armsInterventionsModule", {}).get("interventions", [])
             if i.get("type") in DRUG_TYPES and i.get("name") and not SKIP_RE.search(i["name"])]
    phases = proto.get("designModule", {}).get("phases", []) or []
    phase = max((PHASE_RANK.get(p, 0) for p in phases), default=0)
    return nct, names, phase


def count_trials(indication: str, drug_name: str) -> int:
    params = {"pageSize": 1, "format": "json", "countTotal": "true",
              "query.cond": indication, "query.intr": drug_name, "fields": "NCTId"}
    return int(get_json(CT_URL, params).get("totalCount") or 0)


def trial_stats(indication: str, drug_name: str) -> tuple[int, float]:
    """(number of trials, highest phase) for the drug in the indication."""
    studies = ct_studies(indication, drug_name, pages=1)
    best = max((parse_study(s)[2] for s in studies), default=0)
    try:
        total = count_trials(indication, drug_name)
    except Exception:
        total = len(studies)
    return total or len(studies), best


# ------------------------------------------------------------ main logic

def resolve(class_text: str, indication: str, max_members: int = 5) -> dict:
    symbol = target_symbol(class_text)
    notes: list[str] = []
    members: dict[str, dict] = {}

    def add(drug: dict, source: str, trials: int | None = None, phase: float | None = None):
        m = members.setdefault(drug["chembl_id"], {
            "name": (drug.get("name") or "").lower(), "chembl_id": drug["chembl_id"],
            "sources": [], "trials_in_indication": 0, "max_phase": 0})
        if source not in m["sources"]:
            m["sources"].append(source)
        if trials is not None:
            m["trials_in_indication"] = max(m["trials_in_indication"], trials)
        if phase is not None:
            m["max_phase"] = max(m["max_phase"], phase)

    target = None
    try:
        target = find_target(symbol)
    except OTError as e:
        notes.append(f"Open Targets target search failed: {e}")
    if target:
        print(f"[class] target: {target.get('name')} ({target['id']})")
    else:
        notes.append(f"No target found for '{symbol}' in Open Targets.")

    # (b) registry: (1) trials in the indication that mention the target / class,
    #     (2) ALL Phase 3 trials in the indication, because a record often names only the
    #     drug (or a code) and never says "BTK". The Open Targets check below decides
    #     which of these drugs really act on the target.
    counts: dict[str, dict] = {}

    def collect(studies):
        for st in studies:
            nct, names, phase = parse_study(st)
            for n in names:
                key = drug_key(n)
                if len(key) < 4:
                    continue
                c = counts.setdefault(key, {"ncts": set(), "phase": 0})
                c["ncts"].add(nct)
                c["phase"] = max(c["phase"], phase)

    try:
        collect(ct_studies(indication, f'{symbol} OR "{class_text}"'))
    except Exception as e:
        notes.append(f"ClinicalTrials.gov target query failed: {str(e)[:150]}")
    try:
        collect(ct_studies(indication, phase3=True, pages=5))
    except Exception as e:
        notes.append(f"ClinicalTrials.gov Phase 3 query failed: {str(e)[:150]}")

    top = sorted(counts, key=lambda n: -len(counts[n]["ncts"]))[:CANDIDATE_LIMIT]
    print(f"[class] registry candidates in '{indication}': {len(counts)}, checking {len(top)}")
    unresolved = []
    for n in top:
        drug = resolve_name(n, symbol)
        if drug:
            add(drug, "clinicaltrials.gov", len(counts[n]["ncts"]), counts[n]["phase"])
        else:
            unresolved.append(n)
    if unresolved:
        notes.append("Registry interventions not matched to a drug acting on the target "
                     "(comparators or unknown codes): " + ", ".join(unresolved[:40]))

    # (a) Open Targets: every drug acting on the target, kept only if it has trials in the indication
    if target:
        known = drugs_of_target(target["id"], notes)
        print(f"[class] Open Targets drugs on {symbol}: {len(known)}")
        for d in known:
            if d["chembl_id"] in members:
                add(d, "opentargets")
                continue
            v = verified_drug(d["chembl_id"], symbol)
            if not v:
                continue
            try:
                n, phase = trial_stats(indication, v["name"])
            except Exception as e:
                notes.append(f"trial count for {v['name']} failed: {str(e)[:100]}")
                continue
            if n:
                add(v, "opentargets", n, phase)

    # authoritative numbers: one query per member drug (the earlier counts only saw the
    # trials that matched the target / Phase 3 queries)
    for m in members.values():
        try:
            n, p = trial_stats(indication, m["name"])
            m["trials_in_indication"] = max(n, 0)
            m["max_phase"] = max(p, 0) if n else m["max_phase"]
        except Exception as e:
            notes.append(f"trial count for {m['name']} failed: {str(e)[:100]}")

    ranked = sorted((m for m in members.values() if m["trials_in_indication"] > 0),
                    key=lambda m: (-m["max_phase"], -m["trials_in_indication"], m["name"]))
    dropped = [m["name"] for m in ranked[max_members:]]
    return {
        "class": class_text, "indication": indication, "target_symbol": symbol,
        "target_id": (target or {}).get("id"),
        "members": ranked[:max_members], "not_included": dropped, "notes": notes,
        "method": "target from class text -> Open Targets drugs on target + ClinicalTrials.gov "
                  "trials in the indication; each drug verified by its Open Targets mechanism",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("class_text")
    ap.add_argument("indication")
    ap.add_argument("--max", type=int, default=5, help="how many drugs to keep (default 5)")
    args = ap.parse_args()

    result = resolve(args.class_text, args.indication, args.max)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nClass '{args.class_text}' in '{args.indication}': {len(result['members'])} drug(s)")
    for m in result["members"]:
        print(f"  {m['name']:<22} {m['chembl_id']:<14} phase {m['max_phase']:g}  "
              f"trials {m['trials_in_indication']}  ({', '.join(m['sources'])})")
    if result["not_included"]:
        print("  not included (limit): " + ", ".join(result["not_included"]))
    for n in result["notes"]:
        print("  note:", n)
    print(f"Saved: {OUTPUT_PATH}")
    if not result["members"]:
        print('\nNo members found. Pass the drugs yourself: python main.py --drug "<class>" '
              '--drugs "drugA,drugB" --indication "<indication>"')
        sys.exit(2)


if __name__ == "__main__":
    main()