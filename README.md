# AI Biotech Underwriting — Secrethon 2026 (Unobio track: "How to Underwrite Biotech")

Input: **an indication and a drug**. Output: an **Investment Underwriting Report** with a
recommendation (**Invest / Conditional / Do Not Invest**), where every statement can be
traced down to a source quote:

```
Recommendation → Claims → Evidence record → Source (link)
```

The report has 13 sections: recommendation, scientific thesis, human translation thesis,
clinical development plan, competitive landscape, commercial opportunity, capital to next
milestone, key risks, contradictory evidence, critical unknowns, diligence questions,
what would change the conclusion, and sources.

Team: huhwuh.

---

## 1. Quick start

```bash
pip install -r requirements.txt        # google-genai, pydantic, requests, psycopg[binary],
                                       # python-dotenv, streamlit
cp .env.example .env                   # fill in the keys below
python main.py --drug retatrutide --indication obesity
```

When the pipeline finishes, a Streamlit site with the drill-down report opens on its own
(stop with Ctrl+C). Use `--no-ui` to skip it.

`.env` / environment variables (the `.env` file is in `.gitignore`, never commit it):

| Variable | What for |
|---|---|
| `API_KEY` | Gemini API key (claim extraction, report writing) |
| `AACT_USER`, `AACT_PASSWORD` | free account at aact.ctti-clinicaltrials.org (trial results database) |
| `SEC_USER_AGENT` | `"Your Name you@example.com"`, required by SEC EDGAR |
| `EDGAR_ALLOW_UNVERIFIED` | optional, `1` allows a text-search guess of the sponsor (off by default) |

Useful `main.py` options:

```bash
python main.py --from claims            # evidence already collected, start at claim extraction
python main.py --only report            # rebuild only the report (cheapest step)
python main.py --workers 4              # parallel claim extraction
python main.py --out-prefix NAME        # write results/NAME.json / NAME.md / NAME_claims.md
python main.py --extra FILE.json        # add extra (e.g. demo) evidence + claims to the report step
python main.py --compare OLD.json       # compare the new report with an earlier one
python main.py --dry-run                # print the commands, run nothing
python main.py --ui-only                # open the site for existing reports
```

---

## 2. Pipeline

```
                 ┌──────────────── 1. fetch (datagetters/delegator.py, parallel) ───────────────┐
 indication  ──► │ ClinicalTrials.gov · AACT (results, PK, flow) · Europe PMC (PubMed+preprints) │
 + drug          │ Open Targets · openFDA labels · SEC EDGAR · competitors (other Phase 3 programmes)│
                 └───────────────┬───────────────────────────────────────────────────────────────┘
                                 ▼
                      2. split  → results/evidence/*.json          (records: id, source_type, url, text, meta)
                                 ▼
                      3. claims → results/claims.json              (LLM extracts atomic claims, each with an
                                 ▼                                  exact quote, stage, direction, confidence)
                      4. report → results/report.json / .md        (code verifies, LLM writes sections,
                                 ▼                                  LLM triages severity, code enforces policy)
                      5. ui     → app.py (Streamlit drill-down)
```

* **Retrieval** is deliberately two-sided: Europe PMC has a separate *contradiction search*
  (failure, toxicity, discontinuation, futility), plus PK, tissue-distribution and
  epidemiology searches. A zero result is kept as an honest result and ends up under
  *Critical unknowns*.
* **Competitors** come from the registry: active Phase 3 trials of *other* drugs in the same
  indication, grouped by drug. They show who is in the field, not whose drug is better, and
  are never counted in the capital estimate.
* **Claims** are extracted by the LLM, but only kept if the quote is found verbatim in the
  record (`pipeline/build_report.py`, function `prepare_claims`).
* **Report writing** is 6 section calls, a conflicts call, a severity-triage call and a final
  call. Each call only sees the claims relevant to it.

---

## 3. Why the report can be trusted

Evidence and AI inference are separated, and the separation is enforced by code, not by
asking nicely:

| Label | Meaning |
|---|---|
| **[E]** | restates what a single claim (or a plain list of claims) says; numbers must come from the cited claims |
| **[AI]** | the model's own inference; always shown as such |

Checks done in code (`core/validation.py`, `pipeline/build_report.py`):

* the claim quote must exist in the record, otherwise the claim is dropped;
* numbers in a claim must appear in the quote or record metadata, otherwise the claim is
  dropped (`*_dropped_claims.json` lists every dropped claim with the reason);
* truncated quotes are trimmed or dropped; claims whose quote says "low certainty", "not yet
  peer-reviewed" or "company-reported" are forced to low confidence;
* in the **Recommendation**, an [E] statement must rest on exactly one claim, must not be
  low-confidence or a preprint, and its text is replaced by the claim text verbatim;
* an [E] that mixes biology and clinical data, or claims pointing in opposite directions, is
  downgraded to [AI];
* statements about missing data are rewritten as "in the retrieved sources …" and labelled
  [AI] (absence in our sources is not absence in the world); a statement such as "no human
  data" or "no head-to-head data" is removed when the claims actually contain such data;
* claims about *another* named drug are reclassified as neutral competitor information;
* narrow-subpopulation epidemiology noise and caregiver-eligibility claims are dropped;
* **contradictions**: both sides must use the same comparator, at least one claim per side
  must be about the target drug, and "conflicts" that the model itself calls a non-contradiction
  are removed;
* claim ids are stripped from prose (they are shown only as links to claims);
* a coverage check lists important supporting/contradicting claims that no section used.

Everything is visible in the Streamlit site: click a statement → claims → exact quote → source
link; the *Contradictions* tab shows both sides; *Run & sources* shows the checks.

### 3.1 Critical findings: the model judges, the code enforces

Some single findings can end a programme on their own (a death attributed to the drug, a
regulatory halt, a safety-driven termination). We do **not** hard-code a list of such events,
because any list would miss the next kind of event. Instead:

1. **Severity triage (LLM call).** A separate call reads every contradicting claim and every
   safety/regulatory claim and rates it `critical`, `major` or `minor`, with a category
   (for example `death_or_life_threatening_harm`, `regulatory_halt_or_refusal`,
   `programme_termination`, `other_equivalent_weight`) and a one-line reason. A higher rate of
   adverse events versus a comparator is *major*, not critical, unless there are deaths,
   regulatory action or termination.
2. **Validation in code.** A rating is kept only if the claim exists, is about the target drug
   (not a competitor), is not an eligibility criterion, and is not a low-confidence claim
   (low-confidence "critical" is lowered to "major").
3. **Keyword backstop.** A short regex list (FDA clinical hold, drug-related death, programme
   halted for safety) can only *add* critical findings if the model missed them. It never
   removes one. Every flag records who found it (`model`, `keywords`).
4. **Policy.** A verified critical finding lowers the recommendation by one level
   (Invest → Conditional → Do Not Invest). The final model call is told the policy and must
   also state what it would recommend *without* the critical findings; the code computes the
   expected level from that answer and lowers the recommendation if the model did not. The
   report says who applied the rule (`critical_rule_applied_by`: `model`, `code`, `none`).

Because the model writes both the answer and the explanation under the same policy, the text
of the report stays consistent with the final level.

---

## 4. Capital to next milestone

Computed **by code** from registry data, not by the LLM:

1. Phase 3 trials that are not finished are taken from ClinicalTrials.gov / AACT
   (status, planned enrollment, start date, primary completion, lead sponsor).
2. Remaining spend per trial = participants × cost per participant × share of planned time
   still ahead (spend assumed even between start and primary completion; at least 10% always
   left). Trials not started yet count 100%.
3. Cost per participant is an **assumption by therapeutic area** (`AREA_COSTS` in
   `pipeline/build_report.py`: oncology, neurology, immunology, rare disease, cardiometabolic).
   These are order-of-magnitude figures, not published numbers; check them against published
   benchmarks (for example Sertkaya et al., 2016; Moore et al., 2018) before relying on them.
4. The lead sponsor from the registry is matched to an SEC filer. If it is a US filer
   (for example Eli Lilly), the report shows its cash, R&D expense and operating cash flow from
   XBRL, and compares the estimated spend with the cash. Non-SEC sponsors (for example Roche)
   are reported honestly as "not an SEC filer"; no guess is made.

All numbers in this section are labelled as assumptions or inferences.

---

## 5. Reproducibility and cost

* Every LLM call is logged to `results/run_log.jsonl` (stage, model, tokens, seconds, cost
  estimate). Registry/API responses are cached in `.cache/`.
* Model: `gemini-3.1-flash-lite`. Prices are constants in `core/config.py`
  (`PRICE_IN_PER_M = 0.40`, `PRICE_OUT_PER_M = 1.25`, USD per million tokens). **Check them
  against the current Gemini price list**; the figures below scale linearly with them.
* Measured cost for retatrutide / obesity (one drug–indication pair):

| Step | LLM calls | Cost | Time |
|---|---|---|---|
| Claim extraction (~40 evidence parts) | 40 | ≈ $0.10 | ≈ 2.5 min with parallel workers |
| Report (6 sections + conflicts + triage + final) | 9 | ≈ $0.019 | ≈ 45–60 s |
| **Full run** | ~49 | **≈ $0.12** | ≈ 3–4 min |

  The triage call alone costs about $0.001. Re-running only the report (`--only report`) is
  therefore cheap, which is what the demo below uses.
* The LLM is not deterministic: two runs of the same pair can extract slightly different
  claims and, rarely, rate a borderline finding differently. Retrieval and all arithmetic are
  deterministic, and every rating is stored in the report JSON (`severity_triage`,
  `red_flags`, `recommendation_by_model`, `critical_rule_applied_by`).

---

## 6. Demo: new evidence changes the conclusion

The demo uses **synthetic** evidence records (`source_type: demo_synthetic`). They are
clearly marked: the claims are tagged **NEW EVIDENCE** and **SYNTHETIC DEMO, NOT REAL DATA**,
and the report carries a DEMO banner. Nothing synthetic is ever added unless `--extra` is
passed.

Run (from the project root; the evidence and claims from a normal run must already exist):

```bash
# 1. Baseline on real evidence
python main.py --only report --out-prefix report_baseline --no-ui

# 2. Scenario A: FDA clinical hold + fatal liver injury (synthetic)
python main.py --only report --extra extra_claims_demo_hold.json \
               --out-prefix report_hold --compare results/report_baseline.json --no-ui

# 3. Scenario B: head-to-head result without a safety signal (synthetic)
python main.py --only report --extra extra_claims_demo.json \
               --out-prefix report_new --compare results/report_baseline.json --no-ui

# 4. Look at a scenario in the site (Compare tab shows old vs new)
python main.py --ui-only --out-prefix report_hold
```

Observed results (retatrutide in obesity):

| Run | Recommendation | What happened |
|---|---|---|
| `report_baseline` | **Conditional** | strong phase 2/3 efficacy, open safety and evidence gaps; no critical findings |
| `report_hold` | **Do Not Invest** | triage rated the liver-injury death, the FDA clinical hold and the probable causality as *critical*; the model applied the one-level downgrade itself, the code verified it |
| `report_new` | **Conditional** | the new head-to-head result (no superiority vs tirzepatide) appears as [E] evidence in the Recommendation and the "no head-to-head data" statements disappear; triage rated it *major*, not critical, so the level does not move |

The point of the two scenarios: the system does not flip on any new input (B), but it reacts
to a finding that can stop the programme (A), and the finding is recognised by a model
judgement rather than a fixed list. The *Compare* tab and the `--compare` console output show
the old and new recommendation, the new claims, new critical unknowns, critical findings and
the status of each conflict.

---

## 7. Known limitations

* **Sources.** We use registries, PubMed/Europe PMC, Open Targets, openFDA and SEC. Conference
  abstracts, company press releases and investor decks are **not** included, so very recent
  human data is missing. "No human efficacy data" in a report means "none in our sources".
* **Commercial side.** There is no price, payer or sales data and no market model;
  epidemiology comes from a handful of papers found by title search.
* **Cross-study comparisons** (for example retatrutide vs tirzepatide from different trials)
  are inference and are labelled [AI]; only a head-to-head trial counts as direct evidence.
* **Capital.** Phase 3 only; no manufacturing, filing or launch costs. Cost per participant
  and the share of cost already spent are assumptions. A clinical hold is not yet reflected in
  the capital estimate. SEC figures are company-wide, not drug-specific, and exclude debt and
  future financing.
* **Language model.** Claim extraction can miss claims or mislabel direction; code checks catch
  fabricated quotes and numbers, not every wrong interpretation. Severity triage is a model
  judgement: it can over- or under-rate a finding (the keyword backstop only covers the
  most obvious cases), which is why every rating, its reason and its author are shown in the
  report. Occasionally a "gaps" line such as "no human trial results in the provided claims"
  can survive in a section although later sections contain such data; treat gap lines as
  [AI] notes about our sources. Treat the report as a structured starting point for
  diligence, not as investment advice.
* **Sponsor table.** `SPONSORS` in `datagetters/getters/edgar.py` and `SYNONYMS` in
  `datagetters/getters/aact.py` are hand-written search configuration (not evidence) for the
  pre-defined drugs; verify them if ownership changed.

---

## 8. Project layout

```
main.py                 orchestrates the pipeline (fetch → split → claims → report → ui)
app.py                  Streamlit drill-down site (Report / Contradictions / Claims / Compare / Run)
prompts.py              all LLM prompts (extraction, sections, conflicts, triage, final)
core/
  config.py             model name, prices, paths
  validation.py         claim/statement checks, absence rules, triage validation, critical-finding policy
  evidence.py           evidence records and claim preparation helpers
  capital.py            capital-to-milestone estimate and SEC figures
  md_rendering.py       Markdown rendering of the report
  text_utils.py         text helpers
pipeline/
  claim_collector.py    LLM claim extraction
  build_report.py       claim verification, section writing, conflicts, triage, final recommendation
datagetters/
  delegator.py          runs all getters in parallel, de-duplicates, second "refine" phase
  getters/              clinicaltrials, aact, europepmc, opentargets, openfda, edgar, competitors
extra_claims_demo*.json synthetic evidence for the demo (hold = safety/regulatory scenario)
results/                report*.json/.md, report*_claims.md, *_dropped_claims.json,
                        run_log.jsonl, evidence/, claims.json
```
