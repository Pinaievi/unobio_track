"""
getters/aact.py — AACT (Aggregate Analysis of ClinicalTrials.gov), PostgreSQL-база CTTI.

Для кожного випробування створює до чотирьох записів:
  1. Основний запис (nct_aact): дизайн, статус, спонсор. Якщо у випробування є
     опубліковані результати, то в полі text після опису йде блок
     «Primary outcome results:» — значення по групах, порівняння груп із ефектом,
     довірчими інтервалами та p-value. Раніше ці числа лежали лише у вкладеному
     полі meta, і нейронка склеювала з них цитати; тепер їх можна цитувати дослівно.
  2. Популяція й критерії (nct_aact_population): кого беруть у дослідження, критерії
     включення й виключення; якщо є результати, то ще й характеристики учасників
     (вік, стать, ІМТ, вага, HbA1c тощо) по групах.
  3. Рух учасників (nct_aact_flow): скільки почало й завершило, причини виходу.
  4. Фармакокінетика (nct_aact_pk): Cmax, AUC, період напіввиведення, концентрації
     (є лише в випробуваннях з опублікованими результатами).

Записи 2-4 мають ІНШИЙ source_type, ніж основний, тому delegator.py не вважає їх
дублями основного запису.

Потрібно:
  pip install "psycopg[binary]" python-dotenv
  В .env: AACT_USER і AACT_PASSWORD (логін і пароль ДЛЯ БАЗИ, не для сайту)
"""

import os
import re

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from .base import DataGetter, Query

load_dotenv()

HOST = "aact-db.ctti-clinicaltrials.org"
PORT = 5432
DBNAME = "aact"

MAX_STUDIES = 200            # скільки випробувань максимум беремо
CRITERIA_LIMIT = 700         # символів на розділ критеріїв (inclusion / exclusion)
MAX_BASELINE_ROWS = 14       # скільки показників базової характеристики на групу
MAX_DROP_REASONS = 6         # скільки причин виходу показуємо на групу
MAX_PK_OUTCOMES = 4          # скільки фармакокінетичних результатів на випробування
MAX_PK_VALUES = 12           # скільки значень на один фармакокінетичний результат
MAX_PRIMARY_OUTCOMES = 3     # скільки первинних кінцевих точок з результатами на випробування
MAX_PRIMARY_VALUES = 8       # скільки значень по групах на одну кінцеву точку
MAX_COMPARISONS = 6          # скільки порівнянь груп (p-value, інтервали) на одну кінцеву точку
OUTCOME_TITLE_LIMIT = 250    # символів у назві кінцевої точки

SYNONYMS = {"retatrutide": ["LY3437943"]}

# Які показники базової характеристики нас цікавлять (регулярний вираз PostgreSQL).
# \m ... \M — межі слова, щоб "age" не збігалось із "percentage".
BASELINE_PATTERN = (
    r"\mage\M|\msex\M|gender|body mass index|\mbmi\M|body weight|weight|hba1c|glycated|"
    r"glycosylated|\mrace\M|ethnic|duration of|waist"
)

# Які результати вважаємо фармакокінетичними.
PK_PATTERN = (
    r"pharmacokinetic|\m(?:auc|cmax|tmax|t1/2|clearance)|half[- ]life|"
    r"(?:plasma|serum) concentration"
)


# ---------- підключення ----------

def _connect() -> psycopg.Connection:
    user = os.environ.get("AACT_USER")
    password = os.environ.get("AACT_PASSWORD")
    if not user or not password:
        raise RuntimeError(
            "Не задані AACT_USER / AACT_PASSWORD у .env "
            "(реєстрація: https://aact.ctti-clinicaltrials.org/sign_up)"
        )
    return psycopg.connect(
        host=HOST, port=PORT, dbname=DBNAME,
        user=user, password=password,
        connect_timeout=15, row_factory=dict_row,
    )


def safe(conn, label: str, sql: str, params: dict) -> list[dict]:
    """Виконує підзапит. Якщо схема не збіглась, не валимо весь getter:
    друкуємо, який блок пропущено, і повертаємо порожній список."""
    return safe_chain(conn, label, [sql], params)


def safe_chain(conn, label: str, queries: list[str], params: dict) -> list[dict]:
    """Пробує запити по черзі: від найбагатшого до найпростішого.

    Перший запит, що виконався без помилки, дає результат (навіть порожній: це
    означає «даних немає», а не збій). Якщо розширений запит не підійшов до схеми,
    а простий спрацював, друкуємо про це одним рядком. Якщо не спрацював жоден,
    блок пропускаємо, а решта getter працює далі."""
    last = None
    for index, sql in enumerate(queries):
        try:
            rows = conn.execute(sql, params).fetchall()
        except psycopg.Error as e:
            conn.rollback()
            last = (str(e).splitlines() or ["?"])[0]
            continue
        if index > 0:
            print(f"[aact] «{label}»: використано спрощений запит (розширений не підійшов: {last})")
        return rows
    print(f"[aact] блок «{label}» пропущено: {last}")
    return []


# ---------- допоміжні функції ----------

def _s(value) -> str | None:
    """Дати й інші типи -> рядок для JSON."""
    return None if value is None else str(value)


def trim_num(value) -> str:
    """Число без зайвих нулів: 95.0 -> 95, 0.050 -> 0.05."""
    s = str(value)
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


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


def split_criteria(criteria: str) -> tuple[str, str]:
    """Ділить текст критеріїв на (включення, виключення)."""
    text = clean(criteria)
    match = re.search(r"exclusion criteria\s*:?", text, flags=re.I)
    if not match:
        return re.sub(r"^inclusion criteria\s*:?\s*", "", text, flags=re.I), ""
    inclusion = re.sub(r"^inclusion criteria\s*:?\s*", "", text[: match.start()], flags=re.I)
    return inclusion.strip(), text[match.end():].strip()


def fmt_measure(r: dict) -> str:
    """Один показник: 'Age: Mean 55.1 years, Standard Deviation 10.8'."""
    extra = " ".join(x for x in (r.get("classification"), r.get("category")) if x)
    label = f"{r.get('title') or ''} {extra}".strip()
    unit = r.get("units") or ""
    disp = ""
    if r.get("dispersion_value") not in (None, ""):
        disp = f", {r.get('dispersion_type') or 'dispersion'} {r['dispersion_value']}"
    value = f"{r.get('param_type') or ''} {r.get('param_value')} {unit}".strip()
    return re.sub(r"\s+", " ", f"{label}: {value}{disp}").strip()


def fmt_value(v: dict) -> str:
    """Значення первинного результату в одній групі:
    '12 mg: LS Mean -18.8 Percent change (Standard Error 0.7)'."""
    label = " ".join(x for x in (v.get("classification"), v.get("category")) if x)
    label = f" [{label}]" if label else ""
    unit = f" {v['units']}" if v.get("units") else ""
    disp = ""
    if v.get("dispersion_value") not in (None, ""):
        disp = f" ({v.get('dispersion_type') or 'dispersion'} {v['dispersion_value']})"
    value = f"{v.get('param_type') or ''} {v.get('param_value')}".strip()
    return clean(f"{v.get('grp')}{label}: {value}{unit}{disp}")


def fmt_comparison(a: dict) -> str:
    """Порівняння груп:
    '12 mg vs Placebo: LS Mean difference -13.8 (95% CI -15.8 to -11.8), p < 0.001'."""
    estimate = " ".join(x for x in (a.get("param_type"), _s(a.get("param_value"))) if x)

    interval = ""
    low, high = a.get("ci_lower_limit"), a.get("ci_upper_limit")
    if low is not None and high is not None:
        percent = f"{trim_num(a['ci_percent'])}% " if a.get("ci_percent") is not None else ""
        interval = f" ({percent}CI {_s(low)} to {_s(high)})"

    p_text = ""
    if a.get("p_value") not in (None, ""):
        p_text = f", p {a.get('p_value_modifier') or '='} {a['p_value']}"

    who = f"{a['compared_groups']}: " if a.get("compared_groups") else ""
    return clean(f"{who}{estimate}{interval}{p_text}")


def by_trial(rows: list[dict]) -> dict[str, list[dict]]:
    """Групує рядки за номером NCT."""
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["nct_id"], []).append(r)
    return out


def by_key(rows: list[dict], key: str) -> dict:
    """Групує рядки за довільним полем."""
    out: dict = {}
    for r in rows:
        out.setdefault(r[key], []).append(r)
    return out


# ---------- завантаження додаткових даних (кожен блок ізольований) ----------

def load_eligibility(conn, ncts):
    rows = safe(conn, "критерії відбору",
        """SELECT nct_id, population, gender, minimum_age, maximum_age,
                  healthy_volunteers, criteria
           FROM eligibilities WHERE nct_id = ANY(%(ncts)s)""",
        {"ncts": ncts})
    return {r["nct_id"]: r for r in rows}


def load_baseline(conn, ncts):
    measures = safe(conn, "базові характеристики",
        """SELECT bm.nct_id, COALESCE(rg.title, bm.ctgov_group_code) AS grp,
                  bm.title, bm.classification, bm.category, bm.units,
                  bm.param_type, bm.param_value, bm.dispersion_type, bm.dispersion_value
           FROM baseline_measurements bm
           LEFT JOIN result_groups rg ON rg.id = bm.result_group_id
           WHERE bm.nct_id = ANY(%(ncts)s) AND bm.title ~* %(pattern)s
           ORDER BY bm.nct_id, grp""",
        {"ncts": ncts, "pattern": BASELINE_PATTERN})
    counts = safe(conn, "кількість учасників у групах",
        """SELECT bc.nct_id, COALESCE(rg.title, bc.ctgov_group_code) AS grp, bc.count
           FROM baseline_counts bc
           LEFT JOIN result_groups rg ON rg.id = bc.result_group_id
           WHERE bc.nct_id = ANY(%(ncts)s) AND bc.scope ILIKE 'overall'""",
        {"ncts": ncts})
    group_n = {(r["nct_id"], r["grp"]): r["count"] for r in counts}
    return by_trial(measures), group_n


def load_flow(conn, ncts):
    milestones = safe(conn, "рух учасників",
        """SELECT m.nct_id, COALESCE(rg.title, m.ctgov_group_code) AS grp,
                  upper(m.title) AS step, m.count
           FROM milestones m
           LEFT JOIN result_groups rg ON rg.id = m.result_group_id
           WHERE m.nct_id = ANY(%(ncts)s) AND upper(m.title) IN ('STARTED', 'COMPLETED')
           ORDER BY m.nct_id, grp, m.period""",
        {"ncts": ncts})
    drops = safe(conn, "причини виходу з дослідження",
        """SELECT dw.nct_id, COALESCE(rg.title, dw.ctgov_group_code) AS grp,
                  dw.reason, SUM(dw.count) AS n
           FROM drop_withdrawals dw
           LEFT JOIN result_groups rg ON rg.id = dw.result_group_id
           WHERE dw.nct_id = ANY(%(ncts)s)
           GROUP BY dw.nct_id, grp, dw.reason
           ORDER BY dw.nct_id, grp, n DESC""",
        {"ncts": ncts})
    return by_trial(milestones), by_trial(drops)


def load_pk(conn, ncts):
    outcomes = safe(conn, "фармакокінетичні результати",
        """SELECT o.id, o.nct_id, o.title, o.time_frame, o.units
           FROM outcomes o
           WHERE o.nct_id = ANY(%(ncts)s) AND o.title ~* %(pattern)s
           ORDER BY o.nct_id, o.id""",
        {"ncts": ncts, "pattern": PK_PATTERN})
    if not outcomes:
        return {}, {}
    values = safe_chain(conn, "значення фармакокінетики", [
        """SELECT om.outcome_id, COALESCE(rg.title, om.ctgov_group_code) AS grp,
                  om.classification, om.category, om.title, om.units,
                  om.param_type, om.param_value, om.dispersion_type, om.dispersion_value
           FROM outcome_measurements om
           LEFT JOIN result_groups rg ON rg.id = om.result_group_id
           WHERE om.outcome_id = ANY(%(ids)s)
           ORDER BY om.outcome_id, grp""",
        """SELECT om.outcome_id, COALESCE(rg.title, om.ctgov_group_code) AS grp,
                  om.param_type, om.param_value
           FROM outcome_measurements om
           LEFT JOIN result_groups rg ON rg.id = om.result_group_id
           WHERE om.outcome_id = ANY(%(ids)s)
           ORDER BY om.outcome_id, grp""",
    ], {"ids": [o["id"] for o in outcomes]})
    return by_trial(outcomes), by_key(values, "outcome_id")


def load_primary_results(conn, ncts) -> dict[str, list[dict]]:
    """Первинні кінцеві точки з опублікованими результатами:
    значення по групах і порівняння груп (ефект, інтервал, p-value).

    Фармакокінетичні кінцеві точки сюди не беремо: вони йдуть окремим записом (nct_aact_pk).
    Повертає {nct_id: [ {title, time_frame, values, analyses}, ... ]}."""
    outcomes = safe(conn, "первинні кінцеві точки",
        """SELECT o.id, o.nct_id, o.title, o.time_frame
           FROM outcomes o
           WHERE o.nct_id = ANY(%(ncts)s)
             AND o.outcome_type ILIKE 'primary'
             AND o.title !~* %(pk)s
           ORDER BY o.nct_id, o.id""",
        {"ncts": ncts, "pk": PK_PATTERN})
    if not outcomes:
        return {}
    ids = [o["id"] for o in outcomes]

    values = safe_chain(conn, "значення первинних результатів по групах", [
        """SELECT om.outcome_id, COALESCE(rg.title, om.ctgov_group_code) AS grp,
                  om.classification, om.category, om.units,
                  om.param_type, om.param_value, om.dispersion_type, om.dispersion_value
           FROM outcome_measurements om
           LEFT JOIN result_groups rg ON rg.id = om.result_group_id
           WHERE om.outcome_id = ANY(%(ids)s)
           ORDER BY om.outcome_id, om.id""",
        """SELECT om.outcome_id, COALESCE(rg.title, om.ctgov_group_code) AS grp,
                  om.param_type, om.param_value
           FROM outcome_measurements om
           LEFT JOIN result_groups rg ON rg.id = om.result_group_id
           WHERE om.outcome_id = ANY(%(ids)s)
           ORDER BY om.outcome_id, om.id""",
    ], {"ids": ids})

    analyses = safe_chain(conn, "p-value та інтервали первинних результатів", [
        # розширений: які саме групи порівнюються, відсоток інтервалу, знак біля p-value
        """SELECT oa.outcome_id, oa.param_type, oa.param_value,
                  oa.p_value, oa.p_value_modifier,
                  oa.ci_percent, oa.ci_lower_limit, oa.ci_upper_limit, oa.method,
                  (SELECT string_agg(COALESCE(rg.title, oag.ctgov_group_code), ' vs '
                                     ORDER BY oag.ctgov_group_code)
                     FROM outcome_analysis_groups oag
                     LEFT JOIN result_groups rg ON rg.id = oag.result_group_id
                    WHERE oag.outcome_analysis_id = oa.id) AS compared_groups
           FROM outcome_analyses oa
           WHERE oa.outcome_id = ANY(%(ids)s)
           ORDER BY oa.outcome_id, oa.id""",
        # простий: те, що вже працювало раніше
        """SELECT oa.outcome_id, oa.param_type, oa.param_value, oa.p_value,
                  oa.ci_lower_limit, oa.ci_upper_limit, oa.method
           FROM outcome_analyses oa
           WHERE oa.outcome_id = ANY(%(ids)s)
           ORDER BY oa.outcome_id, oa.id""",
    ], {"ids": ids})

    values_by = by_key(values, "outcome_id")
    analyses_by = by_key(analyses, "outcome_id")

    result: dict[str, list[dict]] = {}
    for o in outcomes:
        v = values_by.get(o["id"], [])[:MAX_PRIMARY_VALUES]
        a = analyses_by.get(o["id"], [])[:MAX_COMPARISONS]
        if not v and not a:          # результатів по цій кінцевій точці не опубліковано
            continue
        bucket = result.setdefault(o["nct_id"], [])
        if len(bucket) < MAX_PRIMARY_OUTCOMES:
            bucket.append({
                "title": o["title"], "time_frame": o["time_frame"],
                "values": v, "analyses": a,
            })
    return result


# ---------- текст блоку з результатами ----------

def primary_results_text(outcomes: list[dict]) -> str:
    """Блок «Primary outcome results:» для поля text основного запису.
    Усе записане звичайними реченнями, щоб нейронка могла цитувати дослівно."""
    blocks = []
    for o in outcomes:
        head = f"Outcome: {cut_text(clean(o['title'] or ''), OUTCOME_TITLE_LIMIT)}"
        if o.get("time_frame"):
            head += f" (time frame: {clean(o['time_frame'])})"
        parts = [head + "."]
        if o["values"]:
            parts.append("Values by group: " + "; ".join(fmt_value(v) for v in o["values"]) + ".")
        if o["analyses"]:
            parts.append("Comparisons: " + "; ".join(fmt_comparison(a) for a in o["analyses"]) + ".")
        blocks.append(" ".join(parts))
    return "Primary outcome results: " + " | ".join(blocks)


def primary_analyses_meta(outcomes: list[dict]) -> list[dict]:
    """Ті самі порівняння у структурованому вигляді для meta (як і раніше, до 5 на випробування)."""
    flat: list[dict] = []
    for o in outcomes:
        for a in o["analyses"]:
            if len(flat) >= 5:
                return flat
            flat.append({
                "outcome": o["title"],
                "time_frame": o["time_frame"],
                "compared_groups": a.get("compared_groups"),
                "param_type": a.get("param_type"),
                "param_value": _s(a.get("param_value")),
                "p_value": _s(a.get("p_value")),
                "ci": [_s(a.get("ci_lower_limit")), _s(a.get("ci_upper_limit"))],
                "method": a.get("method"),
            })
    return flat


# ---------- побудова додаткових записів ----------

def companion(nct: str, kind: str, title: str, text: str, meta: dict) -> dict:
    """Додатковий запис до випробування. source_type відрізняється від основного,
    щоб delegator.py не прибрав його як дубль."""
    return {
        "id": f"E_AACT_{nct}_{kind}",
        "source_type": f"nct_aact_{kind}",
        "source_id": nct,
        "url": f"https://clinicaltrials.gov/study/{nct}",
        "title": title,
        "text": text,
        "meta": {"record_kind": kind, "nct_id": nct, **meta},
    }


def population_record(nct, brief_title, elig, baseline_rows, group_n):
    inclusion, exclusion = split_criteria(elig.get("criteria") or "")
    parts = [
        f"Population and eligibility for trial {nct} ({brief_title}).",
        f"Eligible population: {clean(elig.get('population') or '') or 'not stated'}.",
        f"Sex: {elig.get('gender') or 'not stated'}; age: {elig.get('minimum_age') or 'not stated'} "
        f"to {elig.get('maximum_age') or 'not stated'}; "
        f"healthy volunteers: {elig.get('healthy_volunteers') or 'not stated'}.",
    ]
    if inclusion:
        parts.append(f"Inclusion criteria: {cut_text(inclusion, CRITERIA_LIMIT)}")
    if exclusion:
        parts.append(f"Exclusion criteria: {cut_text(exclusion, CRITERIA_LIMIT)}")

    if baseline_rows:
        groups: dict[str, list[dict]] = {}
        for r in baseline_rows:
            groups.setdefault(r["grp"], []).append(r)
        chunks = []
        for grp, items in groups.items():
            n = group_n.get((nct, grp))
            label = f"{grp} (N={n})" if n else grp
            values = "; ".join(fmt_measure(i) for i in items[:MAX_BASELINE_ROWS])
            chunks.append(f"{label}: {values}")
        parts.append("Baseline characteristics of enrolled participants: " + " | ".join(chunks))

    return companion(
        nct, "population", f"Population and eligibility: {brief_title}", " ".join(parts),
        {
            "sex": elig.get("gender"),
            "min_age": elig.get("minimum_age"),
            "max_age": elig.get("maximum_age"),
            "healthy_volunteers": elig.get("healthy_volunteers"),
            "has_baseline_data": bool(baseline_rows),
        },
    )


def flow_record(nct, brief_title, milestones, drops):
    steps: dict[str, dict[str, object]] = {}
    for m in milestones:
        # якщо періодів кілька, лишаємо перше значення для групи й кроку
        steps.setdefault(m["grp"], {}).setdefault(m["step"], m["count"])
    flow_text = "; ".join(
        f"{grp}: started {v.get('STARTED', 'n/a')}, completed {v.get('COMPLETED', 'n/a')}"
        for grp, v in steps.items()
    )

    reasons_by_group: dict[str, list[str]] = {}
    for d in drops:
        bucket = reasons_by_group.setdefault(d["grp"], [])
        if len(bucket) < MAX_DROP_REASONS and d["reason"]:
            bucket.append(f"{d['reason']} ({d['n']})")
    reasons_text = "; ".join(
        f"{grp}: {', '.join(items)}" for grp, items in reasons_by_group.items()
    )

    parts = [f"Participant flow for trial {nct} ({brief_title})."]
    if flow_text:
        parts.append(f"Participants by group: {flow_text}.")
    if reasons_text:
        parts.append(f"Reasons for not completing (number of participants): {reasons_text}.")

    return companion(
        nct, "flow", f"Participant flow: {brief_title}", " ".join(parts),
        {"groups": steps, "dropout_reasons": reasons_by_group},
    )


def pk_record(nct, brief_title, outcomes, values_by_outcome):
    blocks, meta_items = [], []
    for o in outcomes[:MAX_PK_OUTCOMES]:
        vals = values_by_outcome.get(o["id"], [])[:MAX_PK_VALUES]
        formatted = "; ".join(f"{v['grp']}: {fmt_measure(v)}" for v in vals) or "no values reported"
        frame = f" (time frame: {o['time_frame']})" if o.get("time_frame") else ""
        blocks.append(f"{o['title']}{frame}: {formatted}")
        meta_items.append({"outcome": o["title"], "time_frame": o.get("time_frame"),
                           "values_count": len(vals)})

    text = (
        f"Pharmacokinetic outcome measures reported for trial {nct} ({brief_title}). "
        + " || ".join(blocks)
    )
    return companion(nct, "pk", f"Pharmacokinetic results: {brief_title}", text,
                     {"pk_outcomes": meta_items})


# ---------- сам getter ----------

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
            ncts = [r["nct_id"] for r in rows]
            if not ncts:
                return []

            primary = load_primary_results(conn, ncts)
            eligibility = load_eligibility(conn, ncts)
            baseline, group_n = load_baseline(conn, ncts)
            milestones, drops = load_flow(conn, ncts)
            pk_outcomes, pk_values = load_pk(conn, ncts)

        records: list[dict] = []
        for r in rows:
            nct = r["nct_id"]
            brief = r["brief_title"] or nct

            # 1. основний запис: опис випробування + (якщо є) блок з результатами
            outcomes = primary.get(nct, [])
            text = (r["summary"] or "").strip()
            if outcomes:
                results_text = primary_results_text(outcomes)
                text = f"{text}\n\n{results_text}" if text else results_text

            records.append({
                "id": f"E_AACT_{nct}",
                "source_type": "nct_aact",
                "source_id": nct,
                "url": f"https://clinicaltrials.gov/study/{nct}",
                "title": r["official_title"] or r["brief_title"] or "",
                "text": text,
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
                    "has_primary_results_in_text": bool(outcomes),
                    "conditions": r["conditions"] or [],
                    "interventions": r["interventions"] or [],
                    "lead_sponsor": r["lead_sponsor"],
                    "primary_outcomes": (r["primary_outcomes"] or [])[:3],
                    "primary_analyses": primary_analyses_meta(outcomes),
                },
            })

            # 2. популяція й критерії (+ базові характеристики, якщо є результати)
            elig = eligibility.get(nct)
            if elig and (elig.get("criteria") or elig.get("population")):
                records.append(population_record(
                    nct, brief, elig, baseline.get(nct, []), group_n))

            # 3. рух учасників і причини виходу (лише коли є результати)
            if milestones.get(nct) or drops.get(nct):
                records.append(flow_record(nct, brief, milestones.get(nct, []), drops.get(nct, [])))

            # 4. фармакокінетика (лише коли є результати)
            if pk_outcomes.get(nct):
                records.append(pk_record(nct, brief, pk_outcomes[nct], pk_values))

        return records