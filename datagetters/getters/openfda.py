"""
getters/openfda.py — openFDA (https://open.fda.gov), ключ не обов'язковий.

Що збирає:
  1. Інструкції до препарату (FDA label): показання, чорна рамка-попередження,
     застереження, побічні реакції, механізм дії. Лише для схвалених препаратів.
  2. Побічні ефекти з бази FAERS: скільки повідомлень і які реакції найчастіші.
  3. Якщо вказано захворювання: які схвалені препарати згадують його в показаннях
     (допомагає оцінити конкуренцію, етап 5 завдання).

Якщо препарату в openFDA немає (так буває з усіма неодобреними ліками),
getter додає окремий запис про це, щоб відсутність даних була видна у звіті.

Необов'язково: ключ у .env (OPENFDA_API_KEY=...) підвищує ліміти запитів.
Безкоштовний ключ: https://open.fda.gov/apis/authentication/

Запуск окремо не потрібен: delegator.py знаходить цей файл сам.
"""

import hashlib
import json
import os
import re
import time
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

from .base import CACHE_DIR, HEADERS, DataGetter, Query

load_dotenv()

BASE = "https://api.fda.gov"
LABEL_URL = f"{BASE}/drug/label.json"
EVENT_URL = f"{BASE}/drug/event.json"

MAX_LABELS = 3
TOP_REACTIONS = 10
TOP_COMPETITORS = 500
MAX_LISTED = 150
MAX_NAME_LEN = 60

INDICATION_ALIASES = {
    "obesity": ["weight management", "excess body weight"],
}

SECTIONS = [
    (["indications_and_usage"], "Indications and usage", 600),
    (["boxed_warning"], "Boxed warning", 700),
    (["contraindications"], "Contraindications", 300),
    (["warnings_and_cautions", "warnings"], "Warnings and precautions", 500),
    (["adverse_reactions"], "Adverse reactions", 700),
    (["mechanism_of_action"], "Mechanism of action", 500),
    (["pharmacokinetics"], "Pharmacokinetics", 400),
    (["clinical_studies"], "Clinical studies", 700),
]


class FDAError(RuntimeError):
    """Помилка запиту до openFDA (мережа або неочікувана відповідь)."""



def fda_get(url: str, params: dict) -> dict | None:
    """GET-запит до openFDA. Повертає None, якщо збігів немає (відповідь 404).
    Відповіді (і «нічого не знайдено») кешуються на диск."""
    key = hashlib.sha256((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    path = CACHE_DIR / f"fda_{key}.json"
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        return None if cached.get("_not_found") else cached

    request_params = dict(params)
    api_key = os.environ.get("OPENFDA_API_KEY")
    if api_key:
        request_params["api_key"] = api_key

    last = None
    for attempt in range(3):
        try:
            resp = requests.get(url, params=request_params, headers=HEADERS, timeout=30)
        except requests.RequestException as e:
            last = e
            time.sleep(2 * (attempt + 1))
            continue

        if resp.status_code == 404:
            path.write_text(json.dumps({"_not_found": True}), encoding="utf-8")
            return None

        if resp.status_code in (429, 500, 502, 503, 504):
            last = f"HTTP {resp.status_code}"
            time.sleep(3 * (attempt + 1))
            continue

        try:
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            raise FDAError(f"неочікувана відповідь: {e}")

        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    raise FDAError(f"мережа: {last}")


def public_url(url: str, params: dict) -> str:
    """Посилання, за яким запит можна відтворити в браузері (без ключа API)."""
    return f"{url}?{urlencode(params)}"



def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "x"


def clean(text: str) -> str:
    """Прибирає зайві пробіли й переноси рядків."""
    return re.sub(r"\s+", " ", text or "").strip()


def cut_text(text: str, limit: int) -> str:
    """Обрізає текст по межі речення (або слова), а не посеред слова."""
    if len(text) <= limit:
        return text
    chunk = text[:limit]
    end = chunk.rfind(". ")
    if end > limit * 0.5:
        return chunk[: end + 1]
    return chunk[: chunk.rfind(" ")].rstrip() + "..."


def first_text(value) -> str:
    """Поля інструкції приходять списками рядків; беремо перший непорожній."""
    if isinstance(value, list):
        for item in value:
            if item:
                return clean(str(item))
        return ""
    return clean(str(value or ""))


def pretty_date(yyyymmdd: str | None) -> str | None:
    """20240315 -> 2024-03-15."""
    if yyyymmdd and len(yyyymmdd) == 8 and yyyymmdd.isdigit():
        return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"
    return yyyymmdd


def quote(name: str) -> str:
    """Назва в лапках для пошукового запиту (самі лапки прибираємо)."""
    return '"' + name.replace('"', "") + '"'


def filter_terms(terms: list[dict]) -> tuple[list[dict], int]:
    """Відкидає назви-суміші (гомеопатичні набори з десятками компонентів).

    Ознака суміші: у назві є кома або вона задовга. Звичайні препарати
    (навіть комбіновані, як 'PHENTERMINE AND TOPIRAMATE') проходять,
    бо їхні компоненти з'єднані словом, а не комами.
    Повертає (відфільтрований список, скільки відкинуто).
    """
    kept = [
        t for t in terms
        if "," not in t["term"] and len(t["term"]) <= MAX_NAME_LEN
    ]
    return kept, len(terms) - len(kept)



def label_record(label: dict) -> dict:
    ofda = label.get("openfda") or {}
    brands = ofda.get("brand_name") or []
    generics = ofda.get("generic_name") or []
    set_id = label.get("set_id") or label.get("id")

    parts, included = [], []
    for fields, title, limit in SECTIONS:
        for field in fields:
            body = first_text(label.get(field))
            if body:
                parts.append(f"{title}: {cut_text(body, limit)}")
                included.append(field)
                break

    name = (brands or generics or ["unknown"])[0]
    text = (
        f"FDA drug label for {name} (generic name: {', '.join(generics) or 'not reported'}; "
        f"manufacturer: {', '.join(ofda.get('manufacturer_name') or []) or 'not reported'}). "
        + " ".join(parts)
    )

    return {
        "id": f"E_FDA_label_{set_id}",
        "source_type": "openfda",
        "source_id": set_id,
        "url": f"https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid={set_id}",
        "title": f"FDA drug label: {name}",
        "text": text,
        "meta": {
            "record_kind": "label",
            "brand_names": brands[:5],
            "generic_names": generics[:5],
            "manufacturer": (ofda.get("manufacturer_name") or [None])[0],
            "application_numbers": (ofda.get("application_number") or [])[:5],
            "route": (ofda.get("route") or [])[:3],
            "label_effective_date": pretty_date(label.get("effective_time")),
            "has_boxed_warning": bool(label.get("boxed_warning")),
            "sections_included": included,
        },
    }


def absent_record(mechanism: str, params: dict) -> dict:
    """Запис про те, що препарату в базі інструкцій немає."""
    return {
        "id": f"E_FDA_absent_{slug(mechanism)}",
        "source_type": "openfda",
        "source_id": f"label-search:{mechanism}",
        "url": public_url(LABEL_URL, params),
        "title": f"openFDA drug label search: {mechanism}",
        "text": (
            f"No drug label records matching '{mechanism}' were found in the openFDA "
            f"drug label database (search by generic name, brand name and substance name)."
        ),
        "meta": {"record_kind": "label_search_empty", "query": mechanism, "found": False},
    }


def faers_record(generic: str, total: int, serious: int | None,
                 reactions: list[dict], url: str) -> dict:
    top = "; ".join(f"{r['term']} ({r['count']})" for r in reactions) or "none"
    serious_text = f", of which {serious} are flagged as serious" if serious is not None else ""
    text = (
        f"FDA Adverse Event Reporting System (FAERS) via openFDA for {generic}: "
        f"{total} reports in total{serious_text}. "
        f"Most frequently reported reactions (number of reports): {top}. "
        f"FAERS reports are spontaneous and do not establish that the drug caused the event."
    )
    return {
        "id": f"E_FDA_faers_{slug(generic)}",
        "source_type": "openfda",
        "source_id": f"faers:{generic}",
        "url": url,
        "title": f"FAERS adverse event reports: {generic}",
        "text": text,
        "meta": {
            "record_kind": "faers",
            "generic_name": generic,
            "total_reports": total,
            "serious_reports": serious,
            "top_reactions": reactions,
        },
    }


def indication_record(indication: str, search_terms: list[str],
                      terms: list[dict], omitted: int, url: str) -> dict:
    shown = sorted(t["term"] for t in terms)[:MAX_LISTED]
    omitted_text = (
        f" {omitted} further entries with multi-ingredient names (mostly mixtures) "
        f"were omitted from this list."
        if omitted else ""
    )
    text = (
        f"Drug names (openFDA generic name) whose FDA label text in the indications section "
        f"contains any of these phrases: {', '.join(repr(t) for t in search_terms)}. "
        f"Drugs found: {'; '.join(shown)}.{omitted_text} "
        f"The match is a text search of the indications section, so a drug can appear here "
        f"when its label merely mentions the phrase without being indicated for that condition. "
        f"The list is alphabetical and not ranked by market relevance."
    )
    return {
        "id": f"E_FDA_indication_{slug(indication)}",
        "source_type": "openfda",
        "source_id": f"indication-search:{indication}",
        "url": url,
        "title": f"FDA labels mentioning the indication: {indication}",
        "text": text,
        "meta": {
            "record_kind": "indication_competitors",
            "indication": indication,
            "search_terms": search_terms,
            "omitted_multi_ingredient": omitted,
            "drugs": terms[:MAX_LISTED],
        },
    }



class OpenFDAGetter(DataGetter):
    name = "openfda"

    def fetch(self, query: Query) -> list[dict]:
        if not query.mechanism and not query.indication:
            return []

        records: list[dict] = []
        generics: list[str] = []

        if query.mechanism:
            try:
                records += self._labels(query.mechanism, generics)
            except FDAError as e:
                print(f"[openfda] пошук інструкцій пропущено: {e}")

        for generic in generics[:2]:
            try:
                rec = self._faers(generic)
                if rec:
                    records.append(rec)
            except FDAError as e:
                print(f"[openfda] побічні ефекти для {generic} пропущено: {e}")

        if query.indication:
            try:
                rec = self._indication_competitors(query.indication)
                if rec:
                    records.append(rec)
                else:
                    print(f"[openfda] показання '{query.indication}' в інструкціях не знайдено")
            except FDAError as e:
                print(f"[openfda] пошук за показанням пропущено: {e}")

        return records


    def _labels(self, mechanism: str, generics: list[str]) -> list[dict]:
        n = quote(mechanism)
        params = {
            "search": f"openfda.generic_name:{n} OR openfda.brand_name:{n} "
                      f"OR openfda.substance_name:{n}",
            "limit": 10,
        }
        data = fda_get(LABEL_URL, params)
        results = (data or {}).get("results") or []

        if not results:
            return [absent_record(mechanism, params)]

        results.sort(key=lambda r: r.get("effective_time") or "", reverse=True)
        seen_brands, chosen = set(), []
        for label in results:
            ofda = label.get("openfda") or {}
            brand = ((ofda.get("brand_name") or ofda.get("generic_name") or ["?"])[0]).lower()
            if brand in seen_brands:
                continue
            seen_brands.add(brand)
            chosen.append(label)
            if len(chosen) >= MAX_LABELS:
                break

        records = []
        for label in chosen:
            records.append(label_record(label))
            for g in (label.get("openfda") or {}).get("generic_name") or []:
                if g not in generics:
                    generics.append(g)
        return records

    def _faers(self, generic: str) -> dict | None:
        search = f"patient.drug.openfda.generic_name:{quote(generic)}"

        total_params = {"search": search, "limit": 1}
        total_data = fda_get(EVENT_URL, total_params)
        if not total_data:
            return None
        total = ((total_data.get("meta") or {}).get("results") or {}).get("total") or 0
        if not total:
            return None

        serious_data = fda_get(EVENT_URL, {"search": f"{search} AND serious:1", "limit": 1})
        serious = (((serious_data or {}).get("meta") or {}).get("results") or {}).get("total")

        reactions_params = {
            "search": search,
            "count": "patient.reaction.reactionmeddrapt.exact",
            "limit": TOP_REACTIONS,
        }
        reactions_data = fda_get(EVENT_URL, reactions_params)
        reactions = (reactions_data or {}).get("results") or []

        return faers_record(generic, total, serious, reactions,
                            public_url(EVENT_URL, reactions_params))

    def _indication_competitors(self, indication: str) -> dict | None:
        search_terms = [indication] + INDICATION_ALIASES.get(indication.lower(), [])
        params = {
            "search": " OR ".join(
                f"indications_and_usage:{quote(t)}" for t in search_terms
            ),
            "count": "openfda.generic_name.exact",
            "limit": TOP_COMPETITORS,
        }
        data = fda_get(LABEL_URL, params)
        terms = (data or {}).get("results") or []
        if not terms:
            return None

        kept, omitted = filter_terms(terms)
        if not kept:
            return None
        return indication_record(indication, search_terms, kept, omitted,
                                 public_url(LABEL_URL, params))