"""
getters/europepmc.py — Europe PMC (PubMed + препринти bioRxiv/medRxiv).

Що збирає (кожен запит має свою мітку в meta.found_by):
  1. base_search          — статті за запитом «хвороба AND препарат/механізм».
  2. contradiction_search — невдачі, побічні ефекти, припинені дослідження
                            (завдання вимагає активно шукати докази проти препарату).
  3. pk_search            — фармакокінетика препарату (етап 3: людська експозиція).
                            Препарат має бути в заголовку або анотації статті.
  4. tissue_search        — розподіл у тканинах, залучення мішені (етап 3).
                            Препарат має бути в заголовку або анотації статті.
  5. epidemiology_search  — поширеність і тягар хвороби за останні роки (етап 1).
                            Хвороба й термін епідеміології шукаються в заголовку; потрібні
                            загальні цифри (світ, країна, дорослі): діти, окремі регіони й
                            «тягар, зумовлений хворобою» відсікаються, препринти не беруться.

Нуль результатів у pk_search / tissue_search — чесний результат: для нових препаратів
таких публікацій майже немає, і це має потрапити у «Critical unknowns», а не бути
замаскованим шумом.

Анотації очищаються від HTML-тегів (<sup>2</sup>, <sub>1c</sub>, <h4>) і сутностей (&amp;),
щоб нейронка цитувала той самий текст, що лежить у записі.

Запуск окремо не потрібен: delegator.py знаходить цей файл сам.
"""

import html
import re
from datetime import date

from .base import DataGetter, Query, get_json

URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

# Інші назви препарату (код компанії тощо): шукаємо за ними теж.
SYNONYMS = {"retatrutide": ["LY3437943"]}

# Скільки статей беремо за кожним запитом.
LIMITS = {
    "base_search": 25,
    "contradiction_search": 15,
    "pk_search": 10,
    "tissue_search": 10,
    "epidemiology_search": 10,
}

# Якщо суворий запит епідеміології дав менше статей, ніж це число, пробуємо м'якший.
MIN_RESULTS = 3  # (зараз не використовується: доповнюємо до LIMITS)

# Якщо статтю знайшло кілька запитів, у meta.found_by лишається найважливіша мітка.
TAG_PRIORITY = [
    "contradiction_search",
    "pk_search",
    "tissue_search",
    "epidemiology_search",
    "base_search",
]

# слова, за якими шукаємо докази проти препарату
CONTRA_TERMS = (
    '(failure OR "failed" OR "no benefit" OR discontinued OR toxicity '
    'OR "adverse events" OR futility)'
)

# фармакокінетика: період напіввиведення, експозиція, залежність ефекту від дози
PK_TERMS = (
    '(pharmacokinetics OR pharmacokinetic OR "half-life" OR "exposure-response" '
    'OR "dose-response" OR Cmax OR "drug exposure")'
)

# розподіл у тканинах і залучення мішені
TISSUE_TERMS = (
    '("tissue distribution" OR biodistribution OR "receptor occupancy" '
    'OR "target engagement" OR "tissue penetration")'
)

# епідеміологія: три рівні запиту від найточнішого до найм'якшого.
# Нам потрібні ЗАГАЛЬНІ цифри для дорослих (світ, США), а не діти, окремі регіони
# чи «тягар іншої хвороби, зумовлений хворобою».
EPI_TITLE_TERMS = ('(TITLE:prevalence OR TITLE:epidemiology OR TITLE:incidence '
                   'OR TITLE:"global burden" OR TITLE:trends)')
EPI_LOOSE_TERMS = '(prevalence OR incidence OR epidemiology OR "burden of disease")'
# широкий охоплення: світ / країна / дорослі
EPI_SCOPE_TERMS = ('(TITLE:global OR TITLE:worldwide OR TITLE:"United States" '
                   'OR TITLE:"US adults" OR TITLE:national OR TITLE:adults '
                   'OR TITLE:"adult population")')
# що відкидаємо: діти, підлітки, «зумовлено», інші хвороби як предмет статті
EPI_EXCLUDE = ('NOT (TITLE:children OR TITLE:childhood OR TITLE:adolescents '
               'OR TITLE:adolescent OR TITLE:pediatric OR TITLE:paediatric '
               'OR TITLE:youth OR TITLE:infants OR TITLE:attributable '
               'OR TITLE:"Latin America" OR TITLE:Africa OR TITLE:"Mendelian" '
               'OR TITLE:mortality OR TITLE:"among adults with" OR TITLE:"among patients" '
               'OR TITLE:"among women" OR TITLE:"among men" OR TITLE:"among individuals with")')
EPI_PUBLISHED = "SRC:MED"   # лише журнальні статті, без препринтів і шуму
EPI_YEARS_BACK = 8      # беремо публікації лише за останні роки


def clean_html(text: str) -> str:
    """Прибирає HTML-теги й сутності з тексту.

    Блокові теги (<p>, <br>, <h4>...) замінюємо пробілом, щоб слова не склеювались.
    Рядкові (<sup>, <sub>, <i>, <b>) видаляємо без пробілу: 'I<sup>2</sup>' -> 'I2',
    'HbA<sub>1c</sub>' -> 'HbA1c'.
    """
    if not text:
        return ""
    text = re.sub(r"</?(?:p|br|div|li|ul|ol|h\d)\b[^>]*>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def quote(term: str) -> str:
    """Назва в лапках для пошукового запиту (самі лапки прибираємо)."""
    return '"' + term.replace('"', "") + '"'


class EuropePMCGetter(DataGetter):
    name = "europepmc"

    def fetch(self, query: Query) -> list[dict]:
        if not query.indication and not query.mechanism:
            return []

        names = []
        if query.mechanism:
            names = [query.mechanism] + SYNONYMS.get(query.mechanism.lower(), [])

        # препарат у будь-якому місці тексту (для основних запитів)
        drug_expr = "(" + " OR ".join(quote(n) for n in names) + ")" if names else ""
        # препарат саме в заголовку або анотації (для PK і тканин: відсікає статті,
        # де він згаданий побіжно)
        drug_ta_expr = (
            "(" + " OR ".join(f"TITLE:{quote(n)} OR ABSTRACT:{quote(n)}" for n in names) + ")"
            if names else ""
        )
        disease_expr = quote(query.indication) if query.indication else ""
        disease_title = f"TITLE:{quote(query.indication)}" if query.indication else ""

        base_q = " AND ".join(p for p in (drug_expr, disease_expr) if p)

        # план запитів: (мітка, суворий запит, запасний запит або None)
        plan = [
            ("base_search", base_q, None),
            ("contradiction_search", f"{base_q} AND {CONTRA_TERMS}", None),
        ]
        if drug_ta_expr:        # PK і тканини стосуються препарату, хвороба не потрібна
            plan.append(("pk_search", f"{drug_ta_expr} AND {PK_TERMS}", None))
            plan.append(("tissue_search", f"{drug_ta_expr} AND {TISSUE_TERMS}", None))
        if disease_title:       # епідеміологія стосується хвороби, препарат не потрібен
            first_year = date.today().year - EPI_YEARS_BACK
            years = f"PUB_YEAR:[{first_year} TO {date.today().year}]"
            base = f"{disease_title} AND {years} AND {EPI_PUBLISHED}"
            plan.append((
                "epidemiology_search",
                # рівень 1: заголовок про поширеність + охоплення світ/дорослі, без дітей
                f"{base} AND {EPI_TITLE_TERMS} AND {EPI_SCOPE_TERMS} {EPI_EXCLUDE}",
                # рівні 2-3 доповнюють до ліміту, якщо рівень 1 дав мало
                [f"{base} AND {EPI_TITLE_TERMS} {EPI_EXCLUDE}",
                 f"{base} AND {EPI_LOOSE_TERMS} {EPI_EXCLUDE}"],
            ))

        merged: dict[str, dict] = {}       # id статті -> запис
        tags: dict[str, list[str]] = {}    # id статті -> мітки запитів, що її знайшли
        counts: dict[str, int] = {}

        for tag, strict_q, fallback_q in plan:
            found = self._safe_search(tag, strict_q)

            # суворий запит дав мало: доповнюємо м'якшими (лише де вони передбачені),
            # зберігаючи порядок: спершу найточніші статті
            if fallback_q:
                fallbacks = fallback_q if isinstance(fallback_q, list) else [fallback_q]
                for fq in fallbacks:
                    if len(found) >= LIMITS[tag]:
                        break
                    print(f"[europepmc] «{tag}»: {len(found)} результатів, "
                          f"доповнюю м'якшим запитом")
                    seen = {r["id"] for r in found}
                    found += [r for r in self._safe_search(tag, fq)
                              if r["id"] not in seen]
                found = found[:LIMITS[tag]]

            counts[tag] = len(found)
            for rec in found:
                rid = rec["id"]
                if rid not in merged:
                    merged[rid] = rec
                    tags[rid] = []
                if tag not in tags[rid]:
                    tags[rid].append(tag)

        # проставляємо мітки в meta
        for rid, rec in merged.items():
            rec["meta"]["found_by"] = min(tags[rid], key=TAG_PRIORITY.index)
            rec["meta"]["found_by_all"] = tags[rid]

        summary = ", ".join(f"{t}: {n}" for t, n in counts.items())
        print(f"[europepmc] знайдено за запитами — {summary}; унікальних статей: {len(merged)}")
        return list(merged.values())

    def _safe_search(self, tag: str, q: str) -> list[dict]:
        """Один запит не повинен валити решту: помилку друкуємо, повертаємо порожній список."""
        try:
            return self._search(q, LIMITS[tag])
        except Exception as e:
            print(f"[europepmc] запит «{tag}» пропущено: {e}")
            return []

    @staticmethod
    def _search(q: str, limit: int) -> list[dict]:
        data = get_json(
            URL,
            {"query": q, "format": "json", "resultType": "core", "pageSize": limit},
        )
        out = []
        for r in data.get("resultList", {}).get("result", []):
            src, rid, pmid = r.get("source", ""), r.get("id", ""), r.get("pmid")
            if not rid:
                continue
            out.append({
                "id": f"E_{src}_{rid}",
                "source_type": "pubmed" if pmid else f"epmc_{src.lower()}",
                "source_id": f"PMID:{pmid}" if pmid else f"{src}:{rid}",
                "url": f"https://europepmc.org/article/{src}/{rid}",
                "title": clean_html(r.get("title", "")),
                "text": clean_html(r.get("abstractText", "")),
                "meta": {
                    "year": r.get("pubYear"),
                    "journal": r.get("journalTitle"),
                    "doi": r.get("doi"),
                    "is_preprint": src == "PPR",
                },
            })
        return out