"""
AACT (Aggregate Analysis of ClinicalTrials.gov) — PostgreSQL-база CTTI.

Відмінність від getters/clinicaltrials.py: тут є результати випробувань
(p-value, довірчі інтервали за первинними результатами), яких немає у
звичайній видачі API.

Потрібно:
  pip install "psycopg[binary]"
  Змінні середовища AACT_USER та AACT_PASSWORD (або файл .env поруч із проєктом).
"""

import os
import dotenv

import psycopg
from psycopg.rows import dict_row

from .base import DataGetter, Query

HOST = "aact-db.ctti-clinicaltrials.org"
PORT = 5432
DBNAME = "aact"
MAX_STUDIES = 200
SYNONYMS = {"retatrutide": ["LY3437943"]}


dotenv.load_dotenv()


def _connect() -> psycopg.Connection:
    user = os.environ["AACT_USER"]
    password = os.environ["AACT_PASSWORD"]
    if not user or not password:
        raise RuntimeError(
            "Не задано AACT_USER / AACT_PASSWORD "
            "(реєстрація:https://aact.ctti-clinicaltrials.org/sign_up)"
        )
    return psycopg.connect(
        host=HOST, port=PORT, dbname=DBNAME,
        user=user, password=password,
        connect_timeout=15, row_factory=dict_row,
    )


def _s(value) -> str | None:
    """Дати та інші типи -> рядок для JSON."""
    return None if value is None else str(value)


class AACTGetter(DataGetter):
    name = "aact"

    def fetch(self, query: Query) -> list[dict]:
        if not query.indication and not query.mechanism:
            return []

        conditions_sql, params = [], {}

        if query.mechanism:
            names = [query.mechanism] + SYNONYMS.get(query.mechanism.lower(), [])
            params["drug_patterns"] = [f"%{n}%" for n in names]
            conditions_sql.append(
                """s.nct_id IN (
                     SELECT nct_id FROM interventions WHERE name ILIKE ANY(%(drug_patterns)s)
                     UNION
                     SELECT nct_id FROM intervention_other_names
                       WHERE name ILIKE ANY(%(drug_patterns)s)
                   )"""
            )
        if query.indication:
            params["cond_pattern"] = f"%{query.indication}%"
            conditions_sql.append(
                "s.nct_id IN (SELECT nct_id FROM conditions WHERE name ILIKE %(cond_pattern)s)"
            )

        params["limit"] = MAX_STUDIES
        where = " AND ".join(conditions_sql)

        studies_sql = f"""
            SELECT
              s.nct_id, s.brief_title, s.official_title, s.overall_status,
              s.why_stopped, s.phase, s.study_type, s.enrollment,
              s.start_date, s.primary_completion_date, s.completion_date,
              s.results_first_submitted_date,
              bs.description AS summary,
              (SELECT array_agg(DISTINCT c.name) FROM conditions c
                 WHERE c.nct_id = s.nct_id) AS conditions,
              (SELECT array_agg(DISTINCT i.name) FROM interventions i
                 WHERE i.nct_id = s.nct_id) AS interventions,
              (SELECT sp.name FROM sponsors sp
                 WHERE sp.nct_id = s.nct_id AND sp.lead_or_collaborator = 'lead'
                 LIMIT 1) AS lead_sponsor,
              (SELECT array_agg(d.measure) FROM design_outcomes d
                 WHERE d.nct_id = s.nct_id AND d.outcome_type = 'primary') AS primary_outcomes
            FROM studies s
            LEFT JOIN brief_summaries bs ON bs.nct_id = s.nct_id
            WHERE {where}
            ORDER BY s.start_date DESC NULLS LAST
            LIMIT %(limit)s
        """

        with _connect() as conn:
            rows = conn.execute(studies_sql, params).fetchall()
            analyses = self._fetch_primary_analyses(conn, [r["nct_id"] for r in rows])

        records = []
        for r in rows:
            nct = r["nct_id"]
            records.append({
                "id": f"E_AACT_{nct}",
                "source_type": "nct_aact",
                "source_id": nct,
                "url": f"https://clinicaltrials.gov/study/{nct}",
                "title": r["official_title"] or r["brief_title"] or "",
                "text": r["summary"] or "",
                "meta": {
                    "brief_title": r["brief_title"],
                    "status": r["overall_status"],
                    "why_stopped": r["why_stopped"],
                    "phase": r["phase"],
                    "study_type": r["study_type"],
                    "enrollment": r["enrollment"],
                    "start_date": _s(r["start_date"]),
                    "primary_completion": _s(r["primary_completion_date"]),
                    "completion": _s(r["completion_date"]),
                    "results_submitted": _s(r["results_first_submitted_date"]),
                    "has_results": r["results_first_submitted_date"] is not None,
                    "conditions": r["conditions"] or [],
                    "interventions": r["interventions"] or [],
                    "lead_sponsor": r["lead_sponsor"],
                    "primary_outcomes": (r["primary_outcomes"] or [])[:3],
                    "primary_analyses": analyses.get(nct, []),
                },
            })
        return records

    @staticmethod
    def _fetch_primary_analyses(conn, ncts: list[str]) -> dict[str, list[dict]]:
        """p-value та довірчі інтервали за первинними результатами.
        Якщо схема змінилася, не валимо весь getter — просто без цих даних."""
        if not ncts:
            return {}
        try:
            rows = conn.execute(
                """
                SELECT o.nct_id, o.title, o.time_frame,
                       oa.param_type, oa.param_value, oa.p_value,
                       oa.ci_lower_limit, oa.ci_upper_limit, oa.method
                FROM outcomes o
                JOIN outcome_analyses oa ON oa.outcome_id = o.id
                WHERE o.nct_id = ANY(%(ncts)s) AND o.outcome_type ILIKE 'primary'
                """,
                {"ncts": ncts},
            ).fetchall()
        except psycopg.Error as e:
            conn.rollback()
            print(f"[aact] аналіз результатів пропущено: {e}")
            return {}

        out: dict[str, list[dict]] = {}
        for r in rows:
            bucket = out.setdefault(r["nct_id"], [])
            if len(bucket) >= 5:
                continue
            bucket.append({
                "outcome": r["title"],
                "time_frame": r["time_frame"],
                "param_type": r["param_type"],
                "param_value": _s(r["param_value"]),
                "p_value": _s(r["p_value"]),
                "ci": [_s(r["ci_lower_limit"]), _s(r["ci_upper_limit"])],
                "method": r["method"],
            })
        return out