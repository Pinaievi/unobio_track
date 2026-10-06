from .base import DataGetter, Query, get_json

URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

CONTRA_TERMS = (
    '(failure OR "failed" OR "no benefit" OR discontinued OR toxicity '
    'OR "adverse events" OR futility)'
)


class EuropePMCGetter(DataGetter):
    name = "europepmc"

    def fetch(self, query: Query) -> list[dict]:
        parts = [f'"{x}"' for x in (query.indication, query.mechanism) if x]
        if not parts:
            return []
        base_q = " AND ".join(parts)

        records = self._search(base_q, limit=25)
        # отдельный поиск противоречий — требование задания
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
                "title": r.get("title", ""),
                "text": r.get("abstractText", ""),
                "meta": {
                    "year": r.get("pubYear"),
                    "journal": r.get("journalTitle"),
                    "doi": r.get("doi"),
                    "is_preprint": src == "PPR",
                },
            })
        return out