"""
getters/europepmc.py — Europe PMC (PubMed + препринти bioRxiv/medRxiv).

Що збирає:
  1. Статті за запитом «хвороба AND препарат/механізм».
  2. Окремий пошук суперечностей (невдачі, побічні ефекти, припинені дослідження):
     завдання вимагає активно шукати докази проти препарату.

Анотації очищаються від HTML-тегів (<sup>2</sup>, <sub>1c</sub>, <h4>) і сутностей (&amp;),
щоб нейронка цитувала той самий текст, що лежить у записі.

Запуск окремо не потрібен: delegator.py знаходить цей файл сам.
"""

import html
import re

from .base import DataGetter, Query, get_json

URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

# слова, за якими шукаємо докази проти препарату
CONTRA_TERMS = (
    '(failure OR "failed" OR "no benefit" OR discontinued OR toxicity '
    'OR "adverse events" OR futility)'
)


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


class EuropePMCGetter(DataGetter):
    name = "europepmc"

    def fetch(self, query: Query) -> list[dict]:
        parts = [f'"{x}"' for x in (query.indication, query.mechanism) if x]
        if not parts:
            return []
        base_q = " AND ".join(parts)

        records = self._search(base_q, limit=25)

        # окремий пошук суперечностей: ці записи позначаємо, щоб їх було видно далі
        for rec in self._search(f"{base_q} AND {CONTRA_TERMS}", limit=15):
            rec["meta"]["found_by"] = "contradiction_search"
            records.append(rec)
        return records

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