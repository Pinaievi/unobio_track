"""Drill-down інтерфейс до Investment Underwriting Report.

Запуск:  streamlit run app.py
Читає results/*.json (ті, що створює build_report.py) і показує ланцюжок
Рекомендація -> твердження ([E]/[AI]) -> claim -> цитата -> джерело.
"""
import json
import os
from pathlib import Path

import streamlit as st

RESULTS = Path(__file__).parent / "results"

st.set_page_config(page_title="Underwriting drill-down", layout="wide")

REC_COLORS = {"Invest": "#1a7f37", "Conditional": "#b08800", "Do Not Invest": "#cf222e"}
STAGES_ORDER = ["mechanism", "translation", "clinical", "safety_or_failure",
                "competition", "unmet_need", "regulatory"]


# ---------------------------------------------------------------- дані

def list_reports() -> list:
    """Файли звітів: results/*.json, у яких є ключ recommendation."""
    found = []
    for p in sorted(RESULTS.glob("*.json"), key=lambda x: x.stat().st_mtime,
                    reverse=True):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict) and "recommendation" in data and "claims" in data:
            found.append(p)
    return found


@st.cache_data(show_spinner=False)
def load_report(path_str: str, mtime: float) -> dict:
    return json.loads(Path(path_str).read_text(encoding="utf-8"))


def is_synthetic(claim: dict) -> bool:
    return claim.get("source_type") == "demo_synthetic"


# ---------------------------------------------------------------- відображення

def badge(text: str, color: str) -> str:
    return (f"<span style='background:{color};color:white;padding:2px 9px;"
            f"border-radius:10px;font-size:0.8em;font-weight:600'>{text}</span>")


def kind_badge(kind: str) -> str:
    if kind == "evidence":
        return badge("E · evidence", "#1a7f37")
    return badge("AI · inference", "#6639ba")


def dir_badge(direction: str) -> str:
    color = {"supports": "#1a7f37", "contradicts": "#cf222e"}.get(direction, "#6e7781")
    return badge(direction, color)


def render_claim(c: dict, sources: dict):
    """Один claim: текст, мітки, цитата, джерело."""
    marks = [dir_badge(c["direction"]), badge(c["stage"], "#0969da"),
             badge(f"confidence: {c['confidence']}", "#57606a")]
    if c.get("is_extra"):
        marks.append(badge("NEW EVIDENCE", "#bf3989"))
    if is_synthetic(c):
        marks.append(badge("SYNTHETIC DEMO", "#cf222e"))
    with st.container(border=True):
        st.markdown(f"**{c['id']}** " + " ".join(marks), unsafe_allow_html=True)
        st.markdown(c["claim"])
        st.markdown(f"> {c['quote']}")
        if c.get("numbers_outside_quote"):
            st.caption(f"⚠ числа поза цитатою (є деінде в записі): "
                       f"{c['numbers_outside_quote']}")
        src = sources.get(c["evidence_id"], {})
        title = c.get("record_title") or src.get("title") or c["evidence_id"]
        url = c.get("url") or src.get("url")
        line = f"Джерело: **{title}** · `{c['evidence_id']}` · {c.get('source_type', '')}"
        if url:
            line += f" · [відкрити]({url})"
        st.markdown(line)


def render_statements(items: list, claims: dict, sources: dict, key: str,
                      only_evidence: bool):
    """Список тверджень; кожне розгортається до claims і цитат."""
    for i, s in enumerate(items):
        if only_evidence and s["kind"] != "evidence":
            continue
        ids = s.get("claim_ids", [])
        ev_ids = s.get("evidence_ids", [])
        label = ("[E] " if s["kind"] == "evidence" else "[AI] ") + s["text"]
        if len(label) > 170:
            label = label[:167] + "…"
        with st.expander(label):
            st.markdown(kind_badge(s["kind"]), unsafe_allow_html=True)
            st.markdown(s["text"])
            if s.get("unverified_numbers"):
                st.warning(f"Числа не підтверджені цитованими claims: "
                           f"{s['unverified_numbers']}")
            if s["kind"] == "inference":
                st.caption("Це висновок моделі, а не факт з джерела. Нижче "
                           "claims, на яких він побудований.")
            if ids:
                for cid in ids:
                    if cid in claims:
                        render_claim(claims[cid], sources)
            if ev_ids:
                st.markdown("**Записи реєстру:**")
                for eid in ev_ids:
                    src = sources.get(eid, {})
                    url = src.get("url")
                    st.markdown(f"- `{eid}` {src.get('title', '')}"
                                + (f" · [відкрити]({url})" if url else ""))
            if not ids and not ev_ids:
                st.caption("Для цього твердження немає claims (розрахунок коду "
                           "або обмеження оцінки).")


# ---------------------------------------------------------------- вкладки

def tab_report(rep: dict, claims: dict, sources: dict, only_evidence: bool):
    st.subheader("1. Recommendation")
    render_statements(rep["recommendation_rationale"], claims, sources, "rec",
                      only_evidence)
    for key in ["scientific_thesis", "translation_thesis", "clinical_plan",
                "competitive_landscape", "commercial_opportunity"]:
        sec = rep["sections"][key]
        st.subheader(sec["title"])
        render_statements(sec["statements"], claims, sources, key, only_evidence)
        if sec.get("gaps"):
            st.caption("Gaps: " + "; ".join(sec["gaps"]))
    st.subheader("Capital to next milestone")
    render_statements(rep["capital_to_next_milestone"], claims, sources, "cap",
                      only_evidence)
    calc = rep.get("capital_calc") or {}
    if calc:
        with st.expander("Розрахунок капіталу (код, без LLM)"):
            st.json(calc)
    if rep.get("catalyst_calendar"):
        st.subheader("Catalyst calendar")
        render_statements(rep["catalyst_statements"], claims, sources, "cal", only_evidence)
        rows = rep["catalyst_calendar"]["rows"]
        if rows:
            st.dataframe([{"Date": r["date"] or "—",
                           "Event": r["kind"] + ("" if r.get("in_indication", True)
                                                 else " (other indication)"),
                           "Whose": "competitor" if r["scope"] == "competitor" else "this drug",
                           "Trial": r["nct"] or "—", "Phase": r["phase"],
                           "Status": r["status"], "Sponsor": r["sponsor"] or "—",
                           "Primary endpoint / programme": (r["primary_outcome"] or "—")[:100]}
                          for r in rows], width="stretch")
    if rep.get("pos"):
        st.subheader("Probability of success (benchmark)")
        render_statements(rep["pos_statements"], claims, sources, "pos", only_evidence)
        pos = rep["pos"]
        if pos["rows"] and pos["stage"] not in ("unknown", "approved_or_phase4"):
            st.dataframe([{"Benchmark": r["benchmark"],
                           "Phase 1→2": f"{r['stage_rates']['p1']*100:.1f}%",
                           "Phase 2→3": f"{r['stage_rates']['p2']*100:.1f}%",
                           "Phase 3→NDA/BLA": f"{r['stage_rates']['p3']*100:.1f}%",
                           "NDA/BLA→approval": f"{r['stage_rates']['nda']*100:.1f}%",
                           "PoS to approval from current stage":
                               f"{r['pos_to_approval']*100:.0f}%"} for r in pos["rows"]],
                         width="stretch")
            st.caption("Source: " + pos["source"])
    sec = rep["sections"]["key_risks"]
    st.subheader(sec["title"])
    render_statements(sec["statements"], claims, sources, "risks", only_evidence)
    if sec.get("gaps"):
        st.caption("Gaps: " + "; ".join(sec["gaps"]))

    st.subheader("Critical unknowns")
    for u in rep["critical_unknowns"]:
        st.markdown(f"- {u}")
    st.subheader("Diligence questions")
    for i, q in enumerate(rep["diligence_questions"], 1):
        st.markdown(f"{i}. {q}")
    st.subheader("What would change the conclusion")
    for w in rep["what_would_change_the_conclusion"]:
        st.markdown(f"- {w}")


def tab_conflicts(rep: dict, claims: dict, sources: dict):
    if not rep["conflicts"]:
        st.info("Суперечностей між підтримуючими й заперечуючими claims не знайдено.")
        return
    for c in rep["conflicts"]:
        st.markdown(f"### {c['topic']}")
        st.markdown(f"Статус: **{c['status']}** · endpoint: "
                    f"*{c.get('endpoint', '?')}* · компаратор: "
                    f"*{c.get('shared_comparator', '?')}*")
        st.markdown(kind_badge("inference") + " " + c["assessment"],
                    unsafe_allow_html=True)
        left, right = st.columns(2)
        with left:
            st.markdown("**Підтримують**")
            for cid in c["supporting"]:
                if cid in claims:
                    render_claim(claims[cid], sources)
        with right:
            st.markdown("**Заперечують**")
            for cid in c["contradicting"]:
                if cid in claims:
                    render_claim(claims[cid], sources)


def tab_claims(rep: dict, sources: dict):
    cl = rep["claims"]
    c1, c2, c3, c4 = st.columns(4)
    regions = sorted({c.get("region", "Global") for c in cl})
    f_reg = c4.multiselect("Region", regions, default=regions)
    stages = sorted({c["stage"] for c in cl})
    f_stage = c1.multiselect("Stage", stages, default=stages)
    f_dir = c2.multiselect("Direction", ["supports", "contradicts", "neutral"],
                           default=["supports", "contradicts", "neutral"])
    f_conf = c3.multiselect("Confidence", ["high", "medium", "low"],
                            default=["high", "medium", "low"])
    q = st.text_input("Пошук у тексті claim або цитаті")
    only_new = st.checkbox("Тільки NEW EVIDENCE")
    shown = [c for c in cl
             if c["stage"] in f_stage and c["direction"] in f_dir
             and c["confidence"] in f_conf
             and c.get("region", "Global") in f_reg
             and (not only_new or c.get("is_extra"))
             and (not q or q.lower() in (c["claim"] + c["quote"]).lower())]
    st.caption(f"Показано {len(shown)} з {len(cl)} claims")
    for c in shown[:200]:
        render_claim(c, sources)
    if len(shown) > 200:
        st.caption("Показано перші 200; звузьте фільтр.")


def tab_compare(rep: dict, paths: list):
    st.markdown("Порівняння двох звітів: що змінилося після нових доказів.")
    names = [p.name for p in paths]
    other_name = st.selectbox("Базовий звіт («до»)", names,
                              index=min(1, len(names) - 1))
    other = load_report(str(RESULTS / other_name),
                        (RESULTS / other_name).stat().st_mtime)
    a, b = st.columns(2)
    for col, r, title in [(a, other, "До"), (b, rep, "Після")]:
        color = REC_COLORS.get(r["recommendation"], "#57606a")
        col.markdown(f"**{title}**<br>" + badge(r["recommendation"], color),
                     unsafe_allow_html=True)
    # id перенумеровуються між прогонами, тому claims порівнюємо за записом і цитатою
    def ckey(c):
        return (c.get("evidence_id"), " ".join((c.get("quote") or "").split()))
    old_keys = {ckey(c) for c in other["claims"]}
    new_claims = [c for c in rep["claims"] if ckey(c) not in old_keys]
    st.markdown(f"**Нові claims: {len(new_claims)}**")
    for c in new_claims:
        st.markdown(f"- `{c['id']}` {c['claim']}"
                    + ("  **(SYNTHETIC DEMO)**" if is_synthetic(c) else ""))
    old_u = set(other.get("critical_unknowns", []))
    new_u = [u for u in rep.get("critical_unknowns", []) if u not in old_u]
    st.markdown(f"**Нові критичні невідомі: {len(new_u)}**")
    for u in new_u:
        st.markdown(f"- {u}")
    old_c = {c["topic"]: c["status"] for c in other.get("conflicts", [])}
    for c in rep.get("conflicts", []):
        before = old_c.get(c["topic"])
        if before and before != c["status"]:
            st.markdown(f"**Конфлікт «{c['topic']}»:** {before} → {c['status']}")
    r1, r2 = st.columns(2)
    with r1:
        st.markdown("**Обґрунтування «до»**")
        for s in other["recommendation_rationale"]:
            st.markdown(f"- **[{'E' if s['kind'] == 'evidence' else 'AI'}]** {s['text']}")
    with r2:
        st.markdown("**Обґрунтування «після»**")
        for s in rep["recommendation_rationale"]:
            st.markdown(f"- **[{'E' if s['kind'] == 'evidence' else 'AI'}]** {s['text']}")


def tab_run(rep: dict):
    cost = rep.get("cost", {})
    c1, c2, c3 = st.columns(3)
    c1.metric("LLM викликів", cost.get("calls", "?"))
    c2.metric("Токени (вхід/вихід)",
              f"{cost.get('input_tokens', 0)} / {cost.get('output_tokens', 0)}")
    c3.metric("Вартість кроку звіту, $", f"{cost.get('usd', 0):.4f}")
    st.caption("Ціни моделей у скриптах орієнтовні. Повний журнал: "
               "results/run_log.jsonl")
    st.markdown("**Автоматичні перевірки**")
    if rep.get("issues"):
        for i in rep["issues"]:
            st.markdown(f"- {i}")
    else:
        st.write("Зауважень немає.")
    st.markdown("**Джерела**")
    for s in rep["sources"]:
        link = f" · [відкрити]({s['url']})" if s.get("url") else ""
        st.markdown(f"- `{s['evidence_id']}` ({s['source_type']}) {s['title']}{link}"
                    f" — claims: {', '.join(s['claim_ids']) or '—'}")


# ---------------------------------------------------------------- головна

def main():
    paths = list_reports()
    st.title("Investment Underwriting: drill-down")
    if not paths:
        st.error(f"У {RESULTS} немає звітів (*.json). Спершу запустіть "
                 "python main.py --drug ... --indication ...")
        return

    with st.sidebar:
        st.header("Звіт")
        names = [p.name for p in paths]
        # main.py передає ім'я щойно створеного звіту через змінну середовища
        wanted = os.environ.get("UNDERWRITING_REPORT")
        default_idx = names.index(wanted) if wanted in names else 0
        choice = st.selectbox("Файл", names, index=default_idx)
        only_evidence = st.checkbox("Показувати лише [E] (факти з джерел)")
        st.markdown("**Легенда**")
        st.markdown(kind_badge("evidence") + " твердження переказує один claim "
                    "із цитатою", unsafe_allow_html=True)
        st.markdown(kind_badge("inference") + " висновок моделі на основі claims",
                    unsafe_allow_html=True)
        st.caption("Шлях: Рекомендація → твердження → claim → цитата → джерело. "
                   "Розгорніть будь-яке твердження.")

    path = RESULTS / choice
    rep = load_report(str(path), path.stat().st_mtime)
    claims = {c["id"]: c for c in rep["claims"]}
    sources = {s["evidence_id"]: s for s in rep["sources"]}

    color = REC_COLORS.get(rep["recommendation"], "#57606a")
    st.markdown(f"## {rep['drug']} in {rep['indication']}  "
                + badge(rep["recommendation"], color), unsafe_allow_html=True)
    st.caption(f"Згенеровано {rep['generated']} · claims: {len(rep['claims'])}")
    if rep.get("red_flags"):
        if rep.get("critical_rule_applied_by") == "code":
            step = (f" Модель запропонувала «{rep.get('recommendation_by_model')}», "
                    f"код знизив до «{rep['recommendation']}».")
        else:
            step = " Модель сама застосувала правило; код лише перевірив."
        st.warning("🚩 Правило критичних знахідок: " + "; ".join(
            f"{f['id']} ({'+'.join(f.get('found_by', []))}): {f.get('reason', '')}"
            for f in rep["red_flags"]) + "." + step)
    gate = rep.get("invest_gate") or {}
    if gate.get("checked") and not gate.get("passed"):
        st.info("⚖ Invest gate: модель запропонувала Invest, код знизив до Conditional — "
                + "; ".join(gate.get("reasons", [])))
    if any(is_synthetic(c) for c in rep["claims"]):
        st.error("DEMO: звіт містить СИНТЕТИЧНІ докази (source_type "
                 "demo_synthetic), вигадані лише для перевірки конвеєра. "
                 "Це не реальні дані.")

    t1, t2, t3, t4, t5 = st.tabs(["Report", "Contradictions", "Claims explorer",
                                  "Compare", "Run & sources"])
    with t1:
        tab_report(rep, claims, sources, only_evidence)
    with t2:
        tab_conflicts(rep, claims, sources)
    with t3:
        tab_claims(rep, sources)
    with t4:
        if len(paths) < 2:
            st.info("Для порівняння потрібно щонайменше два звіти в results/.")
        else:
            tab_compare(rep, paths)
    with t5:
        tab_run(rep)


main()