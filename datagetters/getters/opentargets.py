"""
getters/opentargets.py — Open Targets Platform (GraphQL API, ключ не потрібен).

Що збирає:
  1. Препарат: назви, тип, механізм дії, відомі показання.
  2. Мішень (білок/ген), на яку діє препарат: функція, топ асоційованих захворювань.
  3. Зв'язок «мішень – захворювання» для вказаного indication: загальний бал
     та бали за типами доказів (генетика, тварини, клінічні дані тощо).

Це закриває етап 2 завдання (механізм і біологічна валідація).

Запуск окремо не потрібен: delegator.py знаходить цей файл сам.
"""

import hashlib
import json
import time

import requests

from .base import CACHE_DIR, HEADERS, DataGetter, Query

URL = "https://api.platform.opentargets.org/api/v4/graphql"

MAX_DRUGS = 2
MAX_TARGETS = 3
TOP_DISEASES = 100
SHOW_DISEASES = 8
MAX_ASSOC = 3
MIN_ASSOC_SCORE = 0.1
FUNC_LIMIT = 600


class OTError(RuntimeError):
    """Помилка запиту до Open Targets (мережа або схема GraphQL)."""



def gql(query: str, variables: dict | None = None) -> dict:
    """POST-запит до GraphQL. Успішні відповіді кешуються на диск, як в інших getters."""
    variables = variables or {}
    key = hashlib.sha256(
        (URL + query + json.dumps(variables, sort_keys=True)).encode()
    ).hexdigest()
    path = CACHE_DIR / f"ot_{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    last = None
    for attempt in range(3):
        try:
            resp = requests.post(
                URL,
                json={"query": query, "variables": variables},
                headers=HEADERS,
                timeout=30,
            )
        except requests.RequestException as e:
            last = e
            time.sleep(2 * (attempt + 1))
            continue

        if resp.status_code in (429, 500, 502, 503, 504):
            last = f"HTTP {resp.status_code}"
            time.sleep(2 * (attempt + 1))
            continue

        try:
            body = resp.json()
        except ValueError:
            raise OTError(f"response is not JSON (HTTP {resp.status_code})")

        if body.get("errors"):
            msg = "; ".join(e.get("message", "?") for e in body["errors"])
            raise OTError(msg[:1500])

        data = body.get("data") or {}
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    raise OTError(f"network: {last}")



SEARCH_Q = """
query($q: String!, $entities: [String!]) {
  search(queryString: $q, entityNames: $entities, page: {index: 0, size: 5}) {
    hits { id name entity }
  }
}"""

LABEL_TYPE_Q = '{ __type(name: "DrugLabelAndSource") { fields { name } } }'

TARGET_Q = """
query($id: String!, $size: Int!) {
  target(ensemblId: $id) {
    id approvedSymbol approvedName functionDescriptions
    associatedDiseases(page: {index: 0, size: $size}) {
      count
      rows { score disease { id name } datatypeScores { id score } }
    }
  }
}"""

INDICATION_FIELDS = ["maxPhaseForIndication", "maxClinicalStage"]


def label_selection() -> str | None:
    """Ім'я підполя з текстом назви в DrugLabelAndSource (дізнаємось у самого API).
    Якщо дізнатись не вдалось, повертаємо None, і синоніми просто пропускаються."""
    try:
        data = gql(LABEL_TYPE_Q)
    except OTError as e:
        print(f"[opentargets] could not determine the synonym schema: {e}")
        return None
    fields = [f["name"] for f in ((data.get("__type") or {}).get("fields") or [])]
    for candidate in ("label", "name"):
        if candidate in fields:
            return candidate
    return fields[0] if fields else None


def build_drug_query(sel: str | None) -> str:
    """Запит про препарат. Синоніми додаємо лише якщо знаємо їхні підполя."""
    labels_part = f"synonyms {{ {sel} }} tradeNames {{ {sel} }}" if sel else ""
    return f"""
query($id: String!) {{
  drug(chemblId: $id) {{
    id name drugType description {labels_part}
    mechanismsOfAction {{
      rows {{ mechanismOfAction actionType targetName targets {{ id approvedSymbol }} }}
    }}
  }}
}}"""


def labels(items, sel: str | None) -> list[str]:
    """Перетворює список назв (рядки або об'єкти) у простий список рядків."""
    out = []
    for item in items or []:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict) and sel and item.get(sel):
            out.append(str(item[sel]))
    return out


def search(text: str, entities: list[str]) -> list[dict]:
    data = gql(SEARCH_Q, {"q": text, "entities": entities})
    return (data.get("search") or {}).get("hits") or []


def drug_indications(chembl_id: str) -> list[dict]:
    """Показання препарату. Якщо схема змінилась — не валимо весь getter."""
    last = None
    for field in INDICATION_FIELDS:
        q = (
            "query($id: String!) { drug(chemblId: $id) { indications { rows { "
            f"disease {{ id name }} {field} }} }} }}"
        )
        try:
            data = gql(q, {"id": chembl_id})
        except OTError as e:
            last = e
            continue
        rows = ((data.get("drug") or {}).get("indications") or {}).get("rows") or []
        return [
            {"disease_id": r["disease"]["id"], "disease": r["disease"]["name"],
             "max_phase": r.get(field)}
            for r in rows if r.get("disease")
        ]
    print(f"[opentargets] indications for drug {chembl_id} skipped: {last}")
    return []



def fmt_scores(datatype_scores: list[dict]) -> str:
    """Бали за типами доказів, лише ненульові: 'genetic_association 0.12, clinical 0.8'."""
    items = [(d["id"], d["score"]) for d in datatype_scores or [] if d.get("score")]
    items.sort(key=lambda x: x[1], reverse=True)
    return ", ".join(f"{name} {round(score, 3)}" for name, score in items) or "none"


def cut_text(text: str, limit: int) -> str:
    """Обрізає текст по межі речення (або слова), а не посеред слова."""
    if len(text) <= limit:
        return text
    chunk = text[:limit]
    end = max(chunk.rfind(". "), chunk.rfind("; "))
    if end > limit * 0.5:
        return chunk[: end + 1]
    return chunk[: chunk.rfind(" ")].rstrip() + "..."


def drug_matches(drug: dict, query: str) -> bool:
    """Чи справді знайдений препарат відповідає запиту (пошук буває нечітким)."""
    q = query.lower()
    names = [drug.get("name") or ""] + (drug.get("synonyms") or []) + (drug.get("tradeNames") or [])
    return any(q == n.lower() or q in n.lower() for n in names)


def match_indication(rows: list[dict], indication: str, indication_ids: set[str]) -> list[dict]:
    """Вибирає зв'язки мішені саме з тим захворюванням, яке вказав користувач.

    Спершу беремо збіги за ідентифікатором (те, що API вважає цим захворюванням).
    Лише якщо таких немає — запасний пошук за підрядком у назві, і то з порогом
    за балом, щоб рідкісні підтипи (на кшталт 'obesity due to ... deficiency')
    не потрапляли у звіт як шум.
    """
    by_id = [r for r in rows if r["disease"]["id"] in indication_ids]
    if by_id:
        return by_id
    needle = indication.lower()
    return [
        r for r in rows
        if needle in r["disease"]["name"].lower() and r["score"] >= MIN_ASSOC_SCORE
    ]



def drug_record(drug: dict, indications: list[dict], fuzzy: bool) -> dict:
    moa_rows = (drug.get("mechanismsOfAction") or {}).get("rows") or []
    moa_text = "; ".join(
        f"{r.get('mechanismOfAction')} (action type: {r.get('actionType')}; "
        f"target: {r.get('targetName')})"
        for r in moa_rows
    ) or "not reported"

    ind_text = "; ".join(
        f"{i['disease']} (max phase/stage: {i['max_phase']})" for i in indications[:15]
    ) or "none reported"

    text = (
        f"{drug.get('name')} is a {drug.get('drugType')} (ChEMBL ID {drug.get('id')}). "
        f"Mechanisms of action: {moa_text}. "
        f"Indications recorded in Open Targets: {ind_text}."
    )
    if drug.get("description"):
        text += f" Description: {drug['description']}"

    return {
        "id": f"E_OT_drug_{drug['id']}",
        "source_type": "opentargets",
        "source_id": drug["id"],
        "url": f"https://platform.opentargets.org/drug/{drug['id']}",
        "title": f"Open Targets drug profile: {drug.get('name')}",
        "text": text,
        "meta": {
            "record_kind": "drug",
            "chembl_id": drug["id"],
            "drug_type": drug.get("drugType"),
            "synonyms": (drug.get("synonyms") or [])[:10],
            "trade_names": (drug.get("tradeNames") or [])[:10],
            "mechanisms": [
                {"mechanism": r.get("mechanismOfAction"), "action": r.get("actionType"),
                 "target": r.get("targetName")}
                for r in moa_rows
            ],
            "indications": indications[:15],
            "fuzzy_match": fuzzy,
        },
    }


def target_record(target: dict, matched: list[dict], indication: str) -> dict:
    assoc = target.get("associatedDiseases") or {}
    rows = assoc.get("rows") or []
    top = "; ".join(
        f"{r['disease']['name']} (score {round(r['score'], 3)})"
        for r in rows[:SHOW_DISEASES]
    ) or "none"

    func = cut_text((target.get("functionDescriptions") or [""])[0], FUNC_LIMIT)
    text = (
        f"Target {target.get('approvedSymbol')} ({target.get('approvedName')}), "
        f"Ensembl ID {target.get('id')}. "
        f"Function: {func or 'not reported'} "
        f"Number of diseases associated with this target in Open Targets: {assoc.get('count')}. "
        f"Top associated diseases: {top}."
    )
    if indication and not matched:
        text += (
            f" Among the top {TOP_DISEASES} diseases associated with this target, "
            f"none matched '{indication}'."
        )

    return {
        "id": f"E_OT_target_{target['id']}",
        "source_type": "opentargets",
        "source_id": target["id"],
        "url": f"https://platform.opentargets.org/target/{target['id']}",
        "title": f"Open Targets target profile: {target.get('approvedSymbol')}",
        "text": text,
        "meta": {
            "record_kind": "target",
            "ensembl_id": target["id"],
            "symbol": target.get("approvedSymbol"),
            "associated_diseases_total": assoc.get("count"),
            "indication_matched": bool(matched) if indication else None,
        },
    }


def association_record(target: dict, row: dict) -> dict:
    disease = row["disease"]
    text = (
        f"Open Targets association between target {target.get('approvedSymbol')} "
        f"({target.get('approvedName')}) and disease {disease['name']}: "
        f"overall association score {round(row['score'], 3)} (scale 0 to 1). "
        f"Scores by evidence type: {fmt_scores(row.get('datatypeScores'))}."
    )
    return {
        "id": f"E_OT_assoc_{target['id']}_{disease['id']}",
        "source_type": "opentargets",
        "source_id": f"{target['id']}:{disease['id']}",
        "url": f"https://platform.opentargets.org/evidence/{target['id']}/{disease['id']}",
        "title": f"Open Targets association: {target.get('approvedSymbol')} and {disease['name']}",
        "text": text,
        "meta": {
            "record_kind": "target_disease_association",
            "target": target.get("approvedSymbol"),
            "disease": disease["name"],
            "disease_id": disease["id"],
            "score": round(row["score"], 4),
            "datatype_scores": {
                d["id"]: round(d["score"], 4)
                for d in row.get("datatypeScores") or [] if d.get("score")
            },
        },
    }



class OpenTargetsGetter(DataGetter):
    name = "opentargets"

    def fetch(self, query: Query) -> list[dict]:
        if not query.mechanism:
            print("[opentargets] no drug/mechanism given — skipping")
            return []

        records: list[dict] = []

        hits = search(query.mechanism, ["drug", "target"])
        drug_hits = [h for h in hits if (h.get("entity") or "").lower() == "drug"][:MAX_DRUGS]
        target_hits = [h for h in hits if (h.get("entity") or "").lower() == "target"]

        sel = label_selection()
        drug_q = build_drug_query(sel)

        loaded = []
        for h in drug_hits:
            drug = gql(drug_q, {"id": h["id"]}).get("drug")
            if drug:
                drug["synonyms"] = labels(drug.get("synonyms"), sel)
                drug["tradeNames"] = labels(drug.get("tradeNames"), sel)
                loaded.append(drug)

        matching = [d for d in loaded if drug_matches(d, query.mechanism)]
        chosen = matching or loaded[:1]
        fuzzy = not matching

        target_ids: list[str] = []
        for drug in chosen:
            records.append(drug_record(drug, drug_indications(drug["id"]), fuzzy))
            rows = (drug.get("mechanismsOfAction") or {}).get("rows") or []
            for r in rows:
                for t in r.get("targets") or []:
                    if t["id"] not in target_ids:
                        target_ids.append(t["id"])

        for h in target_hits[:2]:
            if h["id"] not in target_ids:
                target_ids.append(h["id"])

        if not records and not target_ids:
            print(f"[opentargets] nothing found for query '{query.mechanism}'")
            return []

        indication_ids: set[str] = set()
        if query.indication:
            for h in search(query.indication, ["disease"])[:3]:
                indication_ids.add(h["id"])

        for tid in target_ids[:MAX_TARGETS]:
            target = gql(TARGET_Q, {"id": tid, "size": TOP_DISEASES}).get("target")
            if not target:
                continue

            rows = (target.get("associatedDiseases") or {}).get("rows") or []
            matched = (
                match_indication(rows, query.indication, indication_ids)
                if query.indication else []
            )

            records.append(target_record(target, matched, query.indication))
            for row in matched[:MAX_ASSOC]:
                records.append(association_record(target, row))

        return records