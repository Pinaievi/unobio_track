import json
from pathlib import Path
from core.text_utils import *
from core.config import *
from core.validation import other_drugs_in

TRUNC_RE = re.compile(r"(?:[;,(=<>±:]|\s[a-z])$")
LOW_CERT_RE = re.compile(
    r"(?i)\b(?:very )?low[- ](?:certainty|quality)\b|not yet peer[- ]reviewed|"
    r"company[- ]reported|press release|unpublished|\bpreliminary (?:data|results)")
YEAR_RE = re.compile(r"^(?:19|20|21)\d\d$")

OTHER_DRUG_STAGES = {"translation", "mechanism", "clinical", "safety_or_failure"}
NOISE_FLOW_ONE_RE = re.compile(r"(?i)\b(?:one|1|two|2) participants?\b")

MIN_QUOTE_LEN = 25
INDICATION_WORDS: set = set()

NOISE_UNMET_RE = re.compile(
    r"(?i)\b(?:veterans?|rural|autis\w*|omega-?\d|social vulnerability|"
    r"hazard ratio|odds ratio|risk of developing|"
    r"associated with (?:an? )?(?:increased|higher|lower|reduced|greater) (?:risk|odds))\b")

NOISE_FLOW_RE = re.compile(r"(?i)lost to follow-?up|withdrawal by subject")
NOISE_ANY_RE = re.compile(
    r"(?i)\b(?:caregivers?|study partners?|informants?|thyroid|anti-?doping|"
    r"doping control|plasma detection window)\b")


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def extract_records(data) -> list:
    """Файли evidence — {"evidence": [...]} або просто список записів."""
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict) and "id" in r]
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict) and "id" in v[0]:
                return v
    return []

def load_evidence(folder: Path) -> dict:
    records = {}
    for p in sorted(folder.glob("*.json")):
        for r in extract_records(load_json(p)):
            records[r["id"]] = r
    return records

def prepare_claims(claims_raw: list, evidence: dict, loose: dict, prefix: str):
    """Присвоюємо id, перевіряємо evidence_id і цитату (по всьому запису).
    Повертаємо (добрі, відкинуті з причиною)."""
    good, dropped = [], []
    n = 1
    for c in claims_raw:
        eid = c.get("evidence_id")
        rec = evidence.get(eid)
        if rec is None:
            dropped.append({"reason": "evidence_id не існує", "claim": c})
            continue
        if eid not in loose:
            loose[eid] = squash(json.dumps(rec, ensure_ascii=False, indent=2))
        if not quote_ok(c.get("quote", ""), loose[eid]):
            dropped.append({"reason": "цитата не знайдена в записі", "claim": c})
            continue
        is_registry = str(rec.get("source_type", "")).startswith("nct")
        if not is_registry and len((c.get("quote") or "").strip()) < MIN_QUOTE_LEN:
            dropped.append({"reason": "цитата надто коротка", "claim": c})
            continue
        q = c.get("quote") or ""
        if len(q) > 400 and q.count(";") >= 8:
            dropped.append({"reason": "шум: цитата — довгий список назв, а не твердження",
                            "claim": c})
            continue
       
        if INDICATION_WORDS and c.get("stage") == "unmet_need" \
                and rec.get("source_type") in ("pubmed", "epmc_pmc", "epmc_ppr") \
                and not any(w in (c.get("claim", "") + " " + c.get("quote", "")).lower()
                            for w in INDICATION_WORDS):
            dropped.append({"reason": "шум: unmet need не про показання", "claim": c})
            continue
        ctext = c.get("claim", "") + " " + c.get("quote", "")
        
        if str(c.get("evidence_id", "")).endswith("_flow") and \
                c.get("direction") == "contradicts" and \
                NOISE_FLOW_ONE_RE.search(c.get("claim", "")):
            dropped.append({"reason": "шум: поодинокий випадок у когорті без порівняння "
                                      "з контролем", "claim": c})
            continue
        if (c.get("direction") == "neutral" and NOISE_FLOW_RE.search(ctext)) or \
                NOISE_ANY_RE.search(ctext) or (
                c.get("stage") == "unmet_need" and NOISE_UNMET_RE.search(ctext)):
            dropped.append({"reason": "шум: вузька підгрупа/асоціація ризику/"
                                      "критерії доглядальника", "claim": c})
            continue

        rec_nums = numbers(json.dumps(rec, ensure_ascii=False))
        claim_nums = numbers(strip_labels(c.get("claim", "")))
        invented = sorted(claim_nums - rec_nums)
        if invented:
            dropped.append({"reason": f"числа {invented} з claim відсутні в записі",
                            "claim": c})
            continue

        c = dict(c)
        q = c.get("quote", "").rstrip()
        if TRUNC_RE.search(q):

            cut = max(q.rfind(ch) for ch in ";,(")
            q2 = q[:cut].rstrip() if cut > 0 else ""
            if len(q2) >= 30 and quote_ok(q2, loose[eid]):
                c["quote"] = q2
                c["quote_trimmed"] = True
            else:
                dropped.append({"reason": "цитата обірвана на півслові", "claim": c})
                continue

        if LOW_CERT_RE.search(c.get("quote", "")) and c.get("confidence") != "low":
            c["confidence"] = "low"
            c["confidence_adjusted"] = "цитата: low certainty / не рецензовано / від компанії"

        if re.search(r"(?i)doping", rec.get("title") or "") and c.get("confidence") != "low":
            c = dict(c)
            c["confidence"] = "low"
            c["confidence_adjusted"] = "назва запису: антидопінгове дослідження малої вибірки"

        backed = numbers(c.get("quote", "")) | numbers(rec.get("title") or "") | numbers(
            json.dumps(rec.get("meta") or {}, ensure_ascii=False))
        outside = sorted(claim_nums - backed)

        dur = set(re.findall(r"(?i)\b(\d+(?:[.,]\d+)?)\s*[- ]?(?:weeks?|wks?|months?|days?)\b",
                             c.get("claim", "")))
        dur_only = [n for n in outside if n in dur or n.replace(",", ".") in dur]
        if dur_only:
            outside = [n for n in outside if n not in dur_only]
            c = dict(c)
            c["duration_from_record"] = dur_only

        unbacked_key = sorted(percent_numbers(c.get("claim", "")) & set(outside))
        if unbacked_key:
            dropped.append({"reason": f"ключові числа {unbacked_key} є в записі, але "
                                      f"не в цитаті claim", "claim": c})
            continue
        unbacked = [n for n in outside if not YEAR_RE.match(n)]
        if unbacked:
            dropped.append({"reason": f"числа {unbacked} є в записі, але не в цитаті "
                                      f"claim й не в meta", "claim": c})
            continue
        item = dict(c)

        if DRUG_NAMES and rec.get("source_type") in ("pubmed", "epmc_pmc", "epmc_ppr"):
            in_claim = any(nm in c.get("claim", "").lower() for nm in DRUG_NAMES)
            in_quote = any(nm in c.get("quote", "").lower() for nm in DRUG_NAMES)
            item["drug_not_in_quote"] = bool(in_claim and not in_quote)

        if DRUG_NAMES and item.get("stage") in OTHER_DRUG_STAGES \
                and item.get("direction") in ("supports", "contradicts") \
                and not any(nm in item.get("claim", "").lower() for nm in DRUG_NAMES):
            others = other_drugs_in(item.get("claim", ""))
            if others:
                item["reclassified_other_drug"] = others
                item["stage"], item["direction"] = "competition", "neutral"

        if DRUG_NAMES and rec.get("source_type") in ("pubmed", "epmc_pmc", "epmc_ppr") \
                and item.get("direction") in ("supports", "contradicts") \
                and item.get("stage") in ("clinical", "safety_or_failure", "translation") \
                and not any(nm in " ".join([item.get("quote", ""),
                                            rec.get("title") or ""]).lower()
                            for nm in DRUG_NAMES):
            item["reclassified_no_target_drug"] = True
            item["stage"], item["direction"] = "other", "neutral"

        item["numbers_outside_quote"] = [n for n in outside if not YEAR_RE.match(n)]
        item["id"] = f"{prefix}{n:03d}"
        item["source_type"] = rec.get("source_type")
        item["record_title"] = rec.get("title")
        item["url"] = rec.get("url")
        item["is_extra"] = prefix != "C"
        good.append(item)
        n += 1
    return good, dropped

def claims_for_prompt(claims: list) -> str:
    rows = []
    for c in claims:
        rows.append(json.dumps({
            "id": c["id"], "stage": c["stage"], "direction": c["direction"],
            "confidence": c["confidence"], "source_type": c["source_type"],
            "claim": c["claim"],
        }, ensure_ascii=False))
    return "\n".join(rows)
