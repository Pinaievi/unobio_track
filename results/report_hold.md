# Investment Underwriting Report: retatrutide in obesity

*Generated: 2026-10-10 05:48:12. Claims used: 144. Run cost: ~$0.0199.*

> ⚠ **DEMO:** this report contains SYNTHETIC evidence (source_type demo_synthetic), invented solely to test the pipeline. This is not real data.

Legend: **[E]** = restates evidence, **[AI]** = AI inference. Ids in brackets are claim ids; every claim with its exact quote is in `report_hold_claims.md`.

## 1. Recommendation: Do Not Invest

> 🚩 **Critical-finding rule.** A separate severity review (a model call, with a keyword backstop) rated these findings as able to stop the programme on their own:
> - X001 (found by model + keywords) [death_or_life_threatening_harm]: Reports of serious drug-induced liver injury and a death attributed to the medication pose a severe threat to the program's safety profile.
> - X002 (found by model + keywords) [regulatory_halt_or_refusal]: A clinical hold by the FDA on all Phase 3 trials is a direct action that halts the entire development program.
> - X003 (found by model) [other_equivalent_weight]: Determined probable causality for liver injury and an unresolved mechanism represent a critical safety risk with significant regulatory implications.
>
> Policy: a critical finding that stops the programme (death, regulatory halt, termination, failed pivotal trial, invalid key result) gives Do Not Invest; any other critical finding lowers the recommendation by one level. The model applied the rule itself and recommended **Do Not Invest**; the code only checked it.

- **[E]** In the TRIUMPH-1 trial, retatrutide achieved a mean body weight reduction of -25.0% at the 12 mg dose versus -3.9% in the placebo group. _[C090]_
- **[E]** The FDA placed the retatrutide obesity programme on clinical hold and enrolment in all Phase 3 trials was paused. _[X002]_
- **[E]** The sponsor reported 4 cases of serious drug-induced liver injury among retatrutide-treated participants in Phase 3 trials, including 1 death from acute liver failure. _[X001]_
- **[E]** Causality to retatrutide was assessed as probable in 3 of the 4 liver injury cases and the mechanism is unresolved. _[X003]_
- **[E]** Permanent treatment discontinuation due to adverse events was more frequent with retatrutide 9 mg (12%) and 12 mg (8%) compared to placebo (5%) in the TRIUMPH-2 trial. _[C089]_
- **[AI]** The sponsor reported four cases of serious drug-induced liver injury, including one death from acute liver failure, with probable causality to the drug in three instances. _[X001, X003]_
- **[AI]** While phase 2 and phase 3 data suggest high efficacy in weight reduction, these results are currently overshadowed by the critical safety concerns regarding severe hepatic injury. _[C053, C090, X001, X003]_
- **[AI]** The reported clinical hold and the unresolved nature of the drug-induced liver injury mechanism constitute a fundamental risk that prevents further investment at this time. _[X001, X002, X003]_

## 2. Scientific thesis

- **[E]** Retatrutide is a triple agonist designed to target the GIP, GLP-1, and glucagon receptors to induce weight loss. _[C083, C094, C105, C116]_
- **[AI]** The glucagon, GLP-1, and GIP receptors are each associated with obesity in scientific databases, with GLP1R having the highest clinical evidence score. _[C134, C136, C137, C139, C140, C141]_
- **[AI]** It is an inference that retatrutide's efficacy in obesity is biologically grounded in the activation of these three distinct receptors, which are individually linked to metabolic and weight-related processes. _[C083, C133, C135, C138, C136, C139]_
- **[E]** In diet-induced obese rats, co-administration of retatrutide and cagrilintide reduces body weight and food intake and improves metabolic health markers. _[C103, C104]_
- **[E]** Animal models have shown that retatrutide can attenuate atrial fibrillation inducibility and inhibit specific pathways associated with renal fibrosis. _[C096, C113]_
- **[AI]** It is an inference that these preclinical outcomes suggest potential benefits beyond direct weight loss, though such findings have not been demonstrated in human obesity trials. _[C096, C113]_
- **[AI]** Evidence regarding retatrutide in humans is limited to a single case report involving a patient with Prader-Willi syndrome and a study showing concentration-dependent increases in contraction force in isolated human atrial preparations. _[C095, C114]_

_Gaps in the data:_ Lack of human clinical trial data confirming the efficacy of retatrutide monotherapy for obesity.; No information on the relative contribution of each individual receptor (GIP, GLP-1, or glucagon) to the overall weight loss effect in humans.; The clinical significance of the isolated atrial contraction force findings remains to be determined.

## 3. Human translation thesis

- **[E]** Retatrutide is a triple agonist targeting the GIP, GLP-1, and glucagon receptors. _[C083, C092, C105, C108, C116, C130, C131, C132]_
- **[E]** In phase 2 trials of adults with obesity and/or T2D, retatrutide was associated with improvements in metabolic health-related lipid and metabolite clusters and significant reductions in various atherogenic lipoproteins. _[C085, C107]_
- **[E]** Retatrutide has a mean half-life of approximately 6 days, which supports a once-weekly dosing regimen. _[C118]_
- **[AI]** As an inference, the observed improvements in metabolic lipid and metabolite clusters in human phase 2 trials suggest that the drug engages its intended biological targets, although the specific biomarkers linking this effect directly to the GIP, GLP-1, and glucagon receptor activation were not explicitly detailed in the provided claims. _[C085, C107]_

_Gaps in the data:_ Sample sizes for the phase 2 trials were not provided in the claims.; Quantitative pharmacokinetic (PK) or pharmacodynamic (PD) data confirming human target engagement (e.g., changes in cAMP levels or receptor occupancy) is not provided.; Data explicitly linking systemic drug exposure to the magnitude of observed clinical effects in humans is missing from the claims.; The specific dose-response relationship of retatrutide monotherapy in humans is not covered by the claims.

## 4. Clinical development plan

- **[E]** Retatrutide is currently being evaluated in a extensive clinical program for obesity and associated metabolic conditions, including Phase 1, 2, and 3 trials. _[C093, C101]_
- **[E]** Phase 2 data showed statistically significant mean percent body weight reductions compared to placebo at 24 weeks, ranging from -5.64% at 1 mg to -12.25% at 4 mg, with further reports of up to 24.2% weight loss at 48 weeks. _[C053, C055, C080]_
- **[E]** The Phase 3 TRIUMPH-1 trial reported a mean body weight reduction of -25.0% for the 12 mg dose compared to -3.9% in the placebo group. _[C090]_
- **[E]** Regulatory records indicate no drug label for retatrutide exists in the openFDA database, though an expanded access program for severe obesity is available. _[C060, C129]_
- **[E]** In a network meta-analysis of adults without diabetes, retatrutide showed the greatest weight loss at -22.10% compared to placebo. _[C097]_
- **[E]** In the 24-week analysis, 4 mg LY3437943 (2 mg titration) demonstrated a statistically significant mean percent body weight reduction compared to placebo with a difference of -10.45% (95% CI -12.21 to -8.7, p < 0.001). _[C054]_
- **[AI]** It is an inference that the program remains in a stage of intensive clinical investigation, given the concurrent execution of various Phase 3 trials and long-term MACE studies, though this is contradicted by synthetic reports of a clinical hold. _[C005, C011, C014, C018, C026, C034, C038, C041, C064, X002]_
- **[AI]** The logical next step for the program is the completion of ongoing Phase 3 and long-term cardiovascular and renal outcome studies to support future regulatory filings. _[C005, C011, C014, C064]_

_Gaps in the data:_ The clinical program has not yet provided long-term safety or efficacy results for most Phase 3 trials, which are required for definitive regulatory assessment.; The contradiction between ongoing trial status and the reported clinical hold is not resolved by the provided claims.; Pediatric clinical data for retatrutide are not covered by the claims.

## 5. Competitive landscape

- **[E]** Several pharmaceutical companies are currently conducting Phase 3 trials for obesity treatments, including semaglutide, tirzepatide, orforglipron, maridebart cafraglutide, NNC0487-0111, cagrilintide, eloralintide, gzr18, berobenatide, zenagamtide, vk2735, and ribupatide. _[C066, C067, C068, C069, C070, C071, C072, C073, C074, C075, C076, C077]_
- **[E]** Retatrutide has been evaluated against active comparators in clinical trials, specifically tirzepatide in trial NCT06662383 and dulaglutide in a Phase 2 trial. _[C019, C106]_
- **[E]** One claim indicates that the FDA has placed the retatrutide obesity program on clinical hold, resulting in a pause of all Phase 3 trial enrollment. _[X002]_
- **[AI]** It is an inference that the clinical hold reported for retatrutide would significantly impact its competitive positioning relative to the multiple Phase 3 obesity programs identified for other agents. _[C066, C067, C068, C069, C070, C071, C072, C073, C074, C075, C076, C077, X002]_
- **[E]** No label records for retatrutide were found in the openFDA database. _[C129]_

_Gaps in the data:_ The provided claims do not contain information regarding specific clinical differentiators or advantages of retatrutide compared to the listed competitors.; The provided claims do not state whether the clinical hold described in a claim has been lifted.

## 6. Commercial opportunity

- **[AI]** The prevalence of obesity in the United States remains high, with reported rates ranging from 40.3% in 2021-2023 to 73.6% for combined overweight and obesity across different jurisdictions in 2021. _[C125, C126]_
- **[AI]** There are numerous competing obesity programs in Phase 3 development, with multiple sponsors collectively planning over 100,000 participant enrollments across various drug candidates like semaglutide, tirzepatide, and orforglipron. _[C066, C067, C068, C069, C070, C071, C072, C073, C074, C075, C076, C077]_ ⚠ unverified numbers: ['100000']
- **[E]** No label records for retatrutide exist in the openFDA database, and a clinical hold has reportedly been placed on the retatrutide obesity program, resulting in a pause of Phase 3 trial enrollment. _[C129, X002]_
- **[AI]** It is an inference that the high prevalence of obesity and overweight in the U.S. represents a significant addressable market, though this is heavily contested by a crowded competitive landscape and current regulatory challenges for retatrutide. _[C125, C126, C066, C067, X002]_

_Gaps in the data:_ No price or sales data were provided, so the total market size in monetary terms is not estimable.; The clinical status of the retatrutide program is currently ambiguous due to the contradiction between ongoing expanded access programs and the reported clinical hold.; Information regarding the specific comparative efficacy or clinical differentiation of retatrutide versus the identified competitors is limited.

## 7. Capital to next milestone

- **[AI]** Next milestone (AI inference from registry status): regulatory submission (some Phase 3 trials have already finished or reported); no Phase 3 trial is enrolling any more, so remaining spend is follow-up and data readout of trials with closed enrollment, plus the filing. _[E_AACT_NCT05882045, E_AACT_NCT05929066, E_AACT_NCT05929079, E_AACT_NCT05931367]_
- **[E]** Lead sponsor(s) of the Phase 3 trials according to the registry: Eli Lilly and Company. _[E_NCT06383390, E_AACT_NCT06662383, E_AACT_NCT06859268, E_AACT_NCT07035093, E_AACT_NCT07232719, E_AACT_NCT07357415, E_AACT_NCT05882045, E_AACT_NCT05929066, E_AACT_NCT05929079, E_AACT_NCT05931367]_
- **[E]** NCT06383390 (A Phase 3, Randomized, Double-Blind, Placebo-Controlled, Event-Driven Study to Investigate): Phase 3, registry status ACTIVE_NOT_RECRUITING (enrollment closed), 10,000 participants planned, start 2024-04-30, primary completion 2029-02-01. _[C064, E_NCT06383390]_
- **[E]** NCT06662383 (A Phase 3, Randomized, Double-Blind Study to Evaluate the Efficacy and Safety of Retatruti): Phase 3, registry status ACTIVE_NOT_RECRUITING (enrollment closed), 800 participants planned, start 2024-11-01, primary completion 2026-11-30. _[C018, C019, E_AACT_NCT06662383]_
- **[E]** NCT06859268 (A Phase 3b, Randomized, Double-Blind, Placebo-Controlled Study to Evaluate Retatrutide Tre): Phase 3, registry status ACTIVE_NOT_RECRUITING (enrollment closed), 643 participants planned, start 2025-03-05, primary completion 2028-04-30. _[C014, C015, E_AACT_NCT06859268]_
- **[E]** NCT07035093 (A Phase 3, Randomized, Double-Blind, Placebo-Controlled Study to Investigate the Efficacy ): Phase 3, registry status ACTIVE_NOT_RECRUITING (enrollment closed), 586 participants planned, start 2025-05-29, primary completion 2027-09-30. _[C011, E_AACT_NCT07035093]_
- **[E]** NCT07232719 (A Phase 3b Study to Investigate the Efficacy and Safety of Retatrutide Once Weekly in Part): Phase 3, registry status ACTIVE_NOT_RECRUITING (enrollment closed), 250 participants planned, start 2025-11-17, primary completion 2027-07-31. _[C008, E_AACT_NCT07232719]_
- **[E]** NCT07357415 (A Phase 3b Study to Investigate the Efficacy and Safety of Different Retatrutide Dose Esca): Phase 3, registry status ACTIVE_NOT_RECRUITING (enrollment closed), 600 participants planned, start 2026-01-24, primary completion 2028-10-31. _[C005, E_AACT_NCT07357415]_
- **[E]** Phase 3 trials excluded because they are completed or have results: NCT05882045, NCT05929066, NCT05929079, NCT05931367. _[E_AACT_NCT05882045, E_AACT_NCT05929066, E_AACT_NCT05929079, E_AACT_NCT05931367]_
- **[AI]** AI inference with an ASSUMPTION that is not from the sources (cost range for the area 'cardiometabolic', spend spread evenly between start and primary completion, at least 10% always left). Trials with known dates: NCT06383390: $73M-$243M (51% of planned time elapsed); NCT06662383: $1M-$4M (93% of planned time elapsed); NCT06859268: $5M-$16M (51% of planned time elapsed); NCT07035093: $4M-$12M (58% of planned time elapsed); NCT07232719: $2M-$6M (53% of planned time elapsed); NCT07357415: $7M-$22M (26% of planned time elapsed). Subtotal about $91M-$303M. Excludes manufacturing, regulatory filing and launch. _[C005, C008, C011, C014, C015, C018, C019, C064, E_NCT06383390, E_AACT_NCT06662383, E_AACT_NCT06859268, E_AACT_NCT07035093, E_AACT_NCT07232719, E_AACT_NCT07357415]_
- **[AI]** AI inference from registry dates: the earliest planned primary completion of these Phase 3 trials is in about 2 months (2026-11-30), the latest in about 28 months (2029-02-01). Primary completion is not the same as results being published. _[E_NCT06383390, E_AACT_NCT06662383, E_AACT_NCT06859268, E_AACT_NCT07035093, E_AACT_NCT07232719, E_AACT_NCT07357415]_
- **[E]** Sponsor funding (SEC EDGAR, company-wide, not specific to this drug) for ELI LILLY & Co (LLY) [registry lead sponsor: Eli Lilly and Company]: cash and cash equivalents $8,950,000,000 as of 2026-06-30; R&D expense $13,337,000,000 for the fiscal year ended 2025-12-31; net operating cash flow $16,813,000,000 for the fiscal year ended 2025-12-31. _[E_SEC_59478]_
- **[AI]** AI inference from the company-wide figures above (ignores other programmes, debt and future financing): the assumed cost of the counted Phase 3 trials ($91M-$303M) is 1%-3% of the current cash. _[E_SEC_59478]_
- **[AI]** Limit of the estimate: Trial status and enrollment are a snapshot of the registry at the time of the search. _[no claims]_
- **[AI]** Limit of the estimate: Cost per participant is an assumed range for the therapeutic area (not from the sources); the share of cost already spent is estimated from elapsed time, not from real progress; real costs differ by trial design, country and duration. _[no claims]_

## 8. Catalyst calendar

- **[E]** Next expected data from the registry: NCT06662383 (Phase 3, ACTIVE_NOT_RECRUITING) primary completion 2026-11-30; primary endpoint: Percent Change from Baseline in Body Weight. Dates come from the registry and can move. _[E_AACT_NCT06662383]_
- **[AI]** Primary completion has passed but no results are in our sources for: NCT05936151, NCT05931367, NCT05882045. Either results exist outside our sources (for example a conference or a press release) or the readout is late; this is a diligence question. _[E_AACT_NCT05936151, E_AACT_NCT05931367, E_AACT_NCT05882045]_
- **[AI]** Competitor Phase 3 programmes with registry dates are listed in the table below; they show when the competitive picture may change, not whose drug is better. _[no claims]_
- **[AI]** Not predicted: regulatory filing and approval dates, and results of trials that are not in the registry. Registry dates are the sponsor's own estimates. _[no claims]_

| Date | Event | Trial | Phase | Status | Sponsor | Primary endpoint / programme |
|---|---|---|---|---|---|---|
| 2022-05-16 | Primary completion passed, results posted in the registry (this drug) | NCT04881760 | Phase 2 | COMPLETED | Eli Lilly and Company | Mean Percent Change From Baseline in Body Weight |
| 2025-10-01 | Primary completion passed, no results in our sources yet (this drug) | NCT05936151 | Phase 2 | COMPLETED | Eli Lilly and Company | Change from Baseline in Glomerular Filtration Rate (mGFR) |
| 2025-11-14 | Primary completion passed, no results in our sources yet (this drug) | NCT05931367 | Phase 3 | COMPLETED | Eli Lilly and Company | Change from Baseline in the Western Ontario and McMaster Universities Osteoarthritis Index |
| 2026-04-06 | Primary completion passed, results reported in the literature (this drug) | NCT05929066 | Phase 3 | COMPLETED | Eli Lilly and Company | Percent Change From Baseline in Body Weight |
| 2026-04-16 | Primary completion passed, no results in our sources yet (this drug) | NCT05882045 | Phase 3 | COMPLETED | Eli Lilly and Company | Percent Change from Baseline in Body Weight |
| 2026-06-16 | Primary completion passed, results reported in the literature (this drug) | NCT05929079 | Phase 3 | COMPLETED | Eli Lilly and Company | Percent Change from Baseline in Body Weight |
| 2026-11-30 | Expected primary data (primary completion) (this drug) | NCT06662383 | Phase 3 | ACTIVE_NOT_RECRUITING | Eli Lilly and Company | Percent Change from Baseline in Body Weight |
| 2027-01-21 | Competitor Phase 3 programme: earliest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 5; RECRUITING 5; NOT_YET_RECRUITING 1 | Amgen | maridebart cafraglutide (11 trials) |
| 2027-03-14 | Expected primary data (primary completion) (this drug) | NCT07467447 | Phase 2 | RECRUITING | Hudson Biotech | Mean percent change in body weight from randomization/baseline to Week 24. |
| 2027-07-01 | Competitor Phase 3 programme: earliest primary completion (competitor) | — | Phase 3 | NOT_YET_RECRUITING 2; ACTIVE_NOT_RECRUITING 2 | Viking Therapeutics, Inc. | vk2735 (4 trials) |
| 2027-07-31 | Expected primary data (primary completion) (this drug) | NCT07232719 | Phase 3 | ACTIVE_NOT_RECRUITING | Eli Lilly and Company | Percent Change from Baseline in Body Weight |
| 2027-09-30 | Expected primary data (primary completion) (this drug) | NCT07035093 | Phase 3 | ACTIVE_NOT_RECRUITING | Eli Lilly and Company | Change from Baseline in Pain Intensity Per Numeric Rating Scale |
| 2028-01-01 | Competitor Phase 3 programme: earliest primary completion (competitor) | — | Phase 3 | RECRUITING 5 | Eli Lilly and Company | eloralintide (5 trials) |
| 2028-02-01 | Competitor Phase 3 programme: earliest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 3; NOT_YET_RECRUITING 1 | Kailera; Fujian Shengdi Pharmaceutical Co., Ltd. | ribupatide (4 trials) |
| 2028-02-16 | Competitor Phase 3 programme: earliest primary completion (competitor) | — | Phase 3 | RECRUITING 1; NOT_YET_RECRUITING 4 | Pfizer | berobenatide (5 trials) |
| 2028-04-30 | Expected primary data (primary completion) (this drug) | NCT06859268 | Phase 3 | ACTIVE_NOT_RECRUITING | Eli Lilly and Company | Percent Change from Baseline in Body Weight |
| 2028-06-01 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | RECRUITING 5 | Eli Lilly and Company | eloralintide (5 trials) |
| 2028-06-06 | Competitor Phase 3 programme: earliest primary completion (competitor) | — | Phase 3 | RECRUITING 8; NOT_YET_RECRUITING 1; ACTIVE_NOT_RECRUITING 1 | Novo Nordisk A/S | nnc0487-0111 (10 trials) |
| 2028-06-27 | Competitor Phase 3 programme: earliest primary completion (competitor) | — | Phase 3 | NOT_YET_RECRUITING 2; RECRUITING 2 | Novo Nordisk A/S | zenagamtide (4 trials) |
| 2028-09-04 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 5; RECRUITING 5; NOT_YET_RECRUITING 1 | Amgen | maridebart cafraglutide (11 trials) |
| 2028-09-28 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | RECRUITING 2; NOT_YET_RECRUITING 2; ACTIVE_NOT_RECRUITING 1 | Gan & Lee Pharmaceuticals. | gzr18 (5 trials) |
| 2028-10-01 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | NOT_YET_RECRUITING 2; ACTIVE_NOT_RECRUITING 2 | Viking Therapeutics, Inc. | vk2735 (4 trials) |
| 2028-10-31 | Expected primary data (primary completion) (this drug) | NCT07357415 | Phase 3 | ACTIVE_NOT_RECRUITING | Eli Lilly and Company | Percent Change from Baseline in Body Weight |
| 2028-11-01 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 3; NOT_YET_RECRUITING 1 | Kailera; Fujian Shengdi Pharmaceutical Co., Ltd. | ribupatide (4 trials) |
| 2029-02-01 | Expected primary data (primary completion) (other indication) (this drug) | NCT06383390 | Phase 3 | ACTIVE_NOT_RECRUITING | Eli Lilly and Company | Time to First Occurrence of Composite Endpoints |
| 2029-03-14 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | RECRUITING 1; NOT_YET_RECRUITING 4 | Pfizer | berobenatide (5 trials) |
| 2029-07-23 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | RECRUITING 8; NOT_YET_RECRUITING 1; ACTIVE_NOT_RECRUITING 1 | Novo Nordisk A/S | nnc0487-0111 (10 trials) |
| 2029-08-01 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 8; RECRUITING 4; NOT_YET_RECRUITING 1 | Eli Lilly and Company | orforglipron (13 trials) |
| 2029-12-01 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 6; NOT_YET_RECRUITING 6; RECRUITING 5 | Eli Lilly and Company; University of Virginia; Woolcock Institute of Medical Research | tirzepatide (17 trials) |
| 2030-03-20 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 4; RECRUITING 2 | Novo Nordisk A/S | cagrilintide (6 trials) |
| 2030-09-16 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | NOT_YET_RECRUITING 2; RECRUITING 2 | Novo Nordisk A/S | zenagamtide (4 trials) |
| 2031-04-30 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 7; RECRUITING 9; NOT_YET_RECRUITING 9 | Novo Nordisk A/S; Kailera; Gan & Lee Pharmaceuticals. | semaglutide (25 trials) |

## 9. Probability of success (benchmark)

- **[AI]** ASSUMPTION from a published benchmark (All indications), not from the drug's own data: the highest phase in the registry is Phase 3, and the average programme at this stage reaches approval about 52% of the time. If the pivotal Phase 3 is positive the benchmark for approval rises to about 91% (NDA/BLA to approval); if it fails the programme stops. _[E_AACT_NCT04881760, E_AACT_NCT05445232, E_AACT_NCT05548231, E_AACT_NCT05882045, E_AACT_NCT05929066, E_AACT_NCT05929079, E_AACT_NCT05931367, E_AACT_NCT05936151, E_AACT_NCT06313528, E_AACT_NCT06662383, E_AACT_NCT06859268, E_AACT_NCT07035093, E_AACT_NCT07232719, E_AACT_NCT07357415, E_AACT_NCT07467447, E_AACT_NCT07629401, E_NCT06039826]_
- **[AI]** ASSUMPTION from a published benchmark (Metabolic), not from the drug's own data: the highest phase in the registry is Phase 3, and the average programme at this stage reaches approval about 56% of the time. If the pivotal Phase 3 is positive the benchmark for approval rises to about 88% (NDA/BLA to approval); if it fails the programme stops. _[E_AACT_NCT04881760, E_AACT_NCT05445232, E_AACT_NCT05548231, E_AACT_NCT05882045, E_AACT_NCT05929066, E_AACT_NCT05929079, E_AACT_NCT05931367, E_AACT_NCT05936151, E_AACT_NCT06313528, E_AACT_NCT06662383, E_AACT_NCT06859268, E_AACT_NCT07035093, E_AACT_NCT07232719, E_AACT_NCT07357415, E_AACT_NCT07467447, E_AACT_NCT07629401, E_NCT06039826]_
- **[AI]** Phase 3 results already reported (registry or literature) for: NCT05929066, NCT05929079. The benchmark does not know them: read the efficacy and safety sections to judge whether this asset is above or below the average. _[E_AACT_NCT04881760, E_AACT_NCT05445232, E_AACT_NCT05548231, E_AACT_NCT05882045, E_AACT_NCT05929066, E_AACT_NCT05929079, E_AACT_NCT05931367, E_AACT_NCT05936151, E_AACT_NCT06313528, E_AACT_NCT06662383, E_AACT_NCT06859268, E_AACT_NCT07035093, E_AACT_NCT07232719, E_AACT_NCT07357415, E_AACT_NCT07467447, E_AACT_NCT07629401, E_NCT06039826]_
- **[AI]** The benchmark is an average over many programmes and is not adjusted for this asset's data, class or sponsor; the asset-specific evidence is in the other sections. Critical findings are present (X001, X002, X003): treat the benchmark as an upper bound. _[no claims]_

| Benchmark | Phase 1→2 | Phase 2→3 | Phase 3→NDA/BLA | NDA/BLA→approval | PoS to approval from current stage |
|---|---|---|---|---|---|
| All indications | 52.0% | 28.9% | 57.8% | 90.6% | **52%** |
| Metabolic | 61.8% | 45.0% | 63.6% | 87.5% | **56%** |

Source: BIO, Informa Pharma Intelligence, QLS: Clinical Development Success Rates and Contributing Factors 2011-2020 (2021), https://go.bio.org/rs/490-EHZ-999/images/ClinicalDevelopmentSuccessRates2011_2020.pdf

## 10. Key risks

- **[E]** The FDA has placed the retatrutide obesity program on clinical hold, resulting in a pause of enrollment for all Phase 3 trials. _[X002]_
- **[E]** The sponsor reported four cases of serious drug-induced liver injury in Phase 3 trials, including one death from acute liver failure, with causality assessed as probable in three of the cases. _[X001, X003]_
- **[E]** In the TRIUMPH-2 trial, permanent treatment discontinuation due to adverse events occurred at a rate of 12% in the 9 mg group and 8% in the 12 mg group, compared to 5% for placebo. _[C089]_
- **[AI]** It is an inference that the reported liver injury cases represent a critical safety risk that likely triggered the current clinical hold, given the severity of the outcomes and the probable causality assessment. _[X001, X002, X003]_
- **[E]** Gastrointestinal adverse events such as nausea, vomiting, constipation, and diarrhea are the most common side effects reported with retatrutide use. _[C079, C087, C110, C119]_
- **[AI]** Reports of dysesthesia and a single case involving severe symptoms from an online-purchased product constitute low-to-medium confidence evidence, making them less significant risks than the documented Phase 3 liver injury cases. _[C081, C082]_
- **[AI]** While some meta-analyses indicate no significant difference in serious adverse events versus placebo, this finding is contradicted by the reported liver injury cases in the Phase 3 program. _[C100, X001, X003]_

_Gaps in the data:_ The specific mechanism of the reported drug-induced liver injury is currently unresolved.; Data regarding regulatory interactions beyond the clinical hold notification.; Long-term post-market safety data, as the current evidence is limited to clinical trial cohorts.

## 11. Contradictory evidence

- **Clinical safety profile and trial discontinuation** (unresolved; endpoint: Permanent discontinuation due to adverse events; comparator: placebo)  
  supports: C102; contradicts: C089  
  **[AI]** This conflict is unresolved. Claim C102 suggests a generally comparable safety profile, whereas C089 provides specific, trial-based evidence from TRIUMPH-2 showing higher rates of discontinuation due to adverse events in retatrutide groups compared to placebo. The specific quantitative data in C089 outweighs the general summary in C102.

## 12. Critical unknowns

- Mechanism of the observed drug-induced liver injury
- Evidence that the FDA clinical hold has been lifted
- Long-term safety data in larger populations beyond the reported liver injury cases
- Resolution of the causality and safety concerns by regulatory authorities

## 13. Diligence questions

1. Has the FDA provided specific criteria required to lift the clinical hold on the retatrutide program?
2. What is the specific hepatotoxicity profile (e.g., ALT/AST elevations, bilirubin levels) associated with the liver injury cases identified in the trials?
3. Does the company have a clear path to resuming Phase 3 enrollment, or are additional safety studies required?
4. Are there identifiable genetic or metabolic biomarkers that predispose patients to the liver injury observed?
5. How do the liver toxicity events compare to those observed in other triple-agonist or incretin-based obesity programs?

## 14. What would change the conclusion

- Formal notification from the FDA that the clinical hold has been lifted.
- A transparent disclosure of the investigation into the liver injury cases demonstrating that the risk is manageable or limited to a specific sub-population.
- Data from a safety committee or regulatory body confirming that the death and liver injury cases do not represent an intrinsic drug-related safety failure.

## 15. Sources

- **E_AACT_NCT04881760** (nct_aact) A Phase 2 Study of Once-Weekly LY3437943 Compared With Placebo in Participants Who Have Obesity or Are Overweight With Weight-Related Comorbidities <https://clinicaltrials.gov/study/NCT04881760> — claims: C053, C054, C055
- **E_AACT_NCT05445232** (nct_aact) A Multiple-Dose Drug-Drug Interaction Study to Determine the Effect of LY3437943 on Drug Metabolizing Enzymes <https://clinicaltrials.gov/study/NCT05445232> — claims: —
- **E_AACT_NCT05548231** (nct_aact) A Multiple Dose Escalation Study in Chinese Participants With Overweight BMI or Obesity to Investigate the Safety, Tolerability, Pharmacokinetics, and Pharmacodynamics of LY3437943 <https://clinicaltrials.gov/study/NCT05548231> — claims: —
- **E_AACT_NCT05882045** (nct_aact) A Randomized, Double-Blind, Phase 3 Study to Investigate the Efficacy and Safety of LY3437943 Once Weekly Compared to Placebo in Participants With Severe Obesity and Established Cardiovascular Disease <https://clinicaltrials.gov/study/NCT05882045> — claims: C041
- **E_AACT_NCT05929066** (nct_aact) A Master Protocol to Investigate the Efficacy and Safety of LY3437943 Once Weekly in Participants Without Type 2 Diabetes Who Have Obesity or Overweight: A Randomized, Double-Blind, Placebo-Controlled Trial (TRIUMPH-1) <https://clinicaltrials.gov/study/NCT05929066> — claims: C038
- **E_AACT_NCT05929079** (nct_aact) A Master Protocol to Investigate the Efficacy and Safety of LY3437943 Once Weekly in Participants With Type 2 Diabetes Mellitus Who Have Obesity or Overweight: A Randomized Double-Blind, Placebo-Controlled Trial <https://clinicaltrials.gov/study/NCT05929079> — claims: C034
- **E_AACT_NCT05931367** (nct_aact) A Phase 3 Study to Investigate the Efficacy and Safety of LY3437943 Once Weekly in Participants Who Have Obesity or Overweight and Osteoarthritis of the Knee: A Randomized, Double-Blind, Placebo-Controlled Trial <https://clinicaltrials.gov/study/NCT05931367> — claims: C026
- **E_AACT_NCT05936151** (nct_aact) A Phase 2b, Double-Blind Study to Investigate the Effect of Retatrutide on Renal Function in Participants With Overweight or Obesity and Chronic Kidney Disease With or Without Type 2 Diabetes <https://clinicaltrials.gov/study/NCT05936151> — claims: —
- **E_AACT_NCT06313528** (nct_aact) A Randomized, Double-Blind, Phase 1 Study to Investigate the Effect of LY3437943 Versus Placebo on Calorie Intake and Energy Expenditure in Participants With Obesity Under Calorie Restriction <https://clinicaltrials.gov/study/NCT06313528> — claims: —
- **E_AACT_NCT06662383** (nct_aact) A Phase 3, Randomized, Double-Blind Study to Evaluate the Efficacy and Safety of Retatrutide Compared to Tirzepatide in Adults Who Have Obesity <https://clinicaltrials.gov/study/NCT06662383> — claims: C018, C019
- **E_AACT_NCT06859268** (nct_aact) A Phase 3b, Randomized, Double-Blind, Placebo-Controlled Study to Evaluate Retatrutide Treatment in the Maintenance of Weight Reduction in Individuals With Obesity <https://clinicaltrials.gov/study/NCT06859268> — claims: C014, C015
- **E_AACT_NCT07035093** (nct_aact) A Phase 3, Randomized, Double-Blind, Placebo-Controlled Study to Investigate the Efficacy and Safety of Retatrutide Once Weekly in Participants Who Have Obesity or Overweight and Chronic Low Back Pain <https://clinicaltrials.gov/study/NCT07035093> — claims: C011
- **E_AACT_NCT07232719** (nct_aact) A Phase 3b Study to Investigate the Efficacy and Safety of Retatrutide Once Weekly in Participants Without Type 2 Diabetes Who Have Obesity or Overweight: A Randomized, Double-Blind, Placebo-Controlled Trial <https://clinicaltrials.gov/study/NCT07232719> — claims: C008
- **E_AACT_NCT07357415** (nct_aact) A Phase 3b Study to Investigate the Efficacy and Safety of Different Retatrutide Dose Escalation Schemes in Participants Without Type 2 Diabetes Who Have Obesity or Overweight: A Randomized, Controlled, Double-Blind Trial <https://clinicaltrials.gov/study/NCT07357415> — claims: C005
- **E_AACT_NCT07467447** (nct_aact) A Phase 2 Study of Once-Weekly LY3437943 Compared With Placebo in Participants Who Have Obesity or Are Overweight With Weight-Related Comorbidities <https://clinicaltrials.gov/study/NCT07467447> — claims: —
- **E_AACT_NCT07629401** (nct_aact) Pre-approval Expanded Access of Retatrutide (LY3437943) <https://clinicaltrials.gov/study/NCT07629401> — claims: C060
- **E_COMP_berobenatide** (competitor_registry) Competitor Phase 3 programme in obesity: berobenatide <https://clinicaltrials.gov/search?cond=obesity&intr=berobenatide> — claims: C074
- **E_COMP_cagrilintide** (competitor_registry) Competitor Phase 3 programme in obesity: cagrilintide <https://clinicaltrials.gov/search?cond=obesity&intr=cagrilintide> — claims: C071
- **E_COMP_eloralintide** (competitor_registry) Competitor Phase 3 programme in obesity: eloralintide <https://clinicaltrials.gov/search?cond=obesity&intr=eloralintide> — claims: C072
- **E_COMP_gzr18** (competitor_registry) Competitor Phase 3 programme in obesity: gzr18 <https://clinicaltrials.gov/search?cond=obesity&intr=gzr18> — claims: C073
- **E_COMP_maridebart_cafraglutide** (competitor_registry) Competitor Phase 3 programme in obesity: maridebart cafraglutide <https://clinicaltrials.gov/search?cond=obesity&intr=maridebart+cafraglutide> — claims: C069
- **E_COMP_nnc0487_0111** (competitor_registry) Competitor Phase 3 programme in obesity: nnc0487-0111 <https://clinicaltrials.gov/search?cond=obesity&intr=nnc0487-0111> — claims: C070
- **E_COMP_orforglipron** (competitor_registry) Competitor Phase 3 programme in obesity: orforglipron <https://clinicaltrials.gov/search?cond=obesity&intr=orforglipron> — claims: C068
- **E_COMP_ribupatide** (competitor_registry) Competitor Phase 3 programme in obesity: ribupatide <https://clinicaltrials.gov/search?cond=obesity&intr=ribupatide> — claims: C077
- **E_COMP_semaglutide** (competitor_registry) Competitor Phase 3 programme in obesity: semaglutide <https://clinicaltrials.gov/search?cond=obesity&intr=semaglutide> — claims: C066
- **E_COMP_tirzepatide** (competitor_registry) Competitor Phase 3 programme in obesity: tirzepatide <https://clinicaltrials.gov/search?cond=obesity&intr=tirzepatide> — claims: C067
- **E_COMP_vk2735** (competitor_registry) Competitor Phase 3 programme in obesity: vk2735 <https://clinicaltrials.gov/search?cond=obesity&intr=vk2735> — claims: C076
- **E_COMP_zenagamtide** (competitor_registry) Competitor Phase 3 programme in obesity: zenagamtide <https://clinicaltrials.gov/search?cond=obesity&intr=zenagamtide> — claims: C075
- **E_DEMO_SAFETY_HOLD** (demo_synthetic) [DEMO, SYNTHETIC EVIDENCE, NOT A REAL PUBLICATION] Hypothetical safety notice and FDA clinical hold for retatrutide  — claims: X001, X002, X003
- **E_FDA_absent_retatrutide** (openfda) openFDA drug label search: retatrutide <https://api.fda.gov/drug/label.json?search=openfda.generic_name%3A%22retatrutide%22+OR+openfda.brand_name%3A%22retatrutide%22+OR+openfda.substance_name%3A%22retatrutide%22&limit=10> — claims: C129
- **E_MED_39507873** (pubmed) The "Weight" for a New Agent Is Almost Over: A Commentary on the Novel Triagonist Retatrutide for Obesity. <https://europepmc.org/article/MED/39507873> — claims: C108, C110
- **E_MED_39724554** (pubmed) The First Triple Agonist for Antiobesity: Retatrutide. <https://europepmc.org/article/MED/39724554> — claims: C118, C119
- **E_MED_39817343** (pubmed) Efficacy and safety of triple hormone receptor agonist retatrutide for the management of obesity: a systematic review and meta-analysis. <https://europepmc.org/article/MED/39817343> — claims: C101, C102
- **E_MED_40563436** (pubmed) Retatrutide-A Game Changer in Obesity Pharmacotherapy. <https://europepmc.org/article/MED/40563436> — claims: C116
- **E_MED_40613938** (pubmed) Inotropic effects of retatrutide in isolated human atrial preparations. <https://europepmc.org/article/MED/40613938> — claims: C114
- **E_MED_41297910** (pubmed) Engineered nutrient-stimulated hormonal multi-agonists for precision targeting of obesity and metabolic disorders. <https://europepmc.org/article/MED/41297910> — claims: C105
- **E_MED_41537067** (pubmed) Efficacy and Safety of Retatrutide in the Treatment of Diabetes and/or Obesity Comorbid with Chronic Kidney disease: a Systematic Review and Meta-Analysis. <https://europepmc.org/article/MED/41537067> — claims: C087
- **E_MED_41785010** (pubmed) Retatrutide in type 2 diabetes mellitus and obesity: an overview. <https://europepmc.org/article/MED/41785010> — claims: C079
- **E_MED_41927053** (pubmed) Temporal Trends of the Obesity Epidemic in the United States. <https://europepmc.org/article/MED/41927053> — claims: C125
- **E_MED_42135195** (pubmed) Retatrutide And Lipid And Metabolite Profiles In Participants With Obesity With Or Without Type 2 Diabetes. <https://europepmc.org/article/MED/42135195> — claims: C106, C107
- **E_MED_42156758** (pubmed) Kynurenic acid mediates epicardial fat-induced lymphatic metabolic dysfunction in atrial fibrillation. <https://europepmc.org/article/MED/42156758> — claims: C096
- **E_MED_42165732** (pubmed) Evolution of incretin-based therapies: From GLP-1 monotherapy to dual and triple agonists: A new era in metabolic therapy. <https://europepmc.org/article/MED/42165732> — claims: C093
- **E_MED_42529769** (pubmed) Efficacy and Safety of Dual and Triple Glucagon-Like Peptide-1-Based Polyagonists in Metabolic Dysfunction-Associated Steatotic Liver Disease and Steatohepatitis: A Systematic Review and Meta-Analysis. <https://europepmc.org/article/MED/42529769> — claims: C100
- **E_MED_42530676** (pubmed) Design of a metabolically-stable peptide therapeutic with triple-hormone-receptor agonist activity. <https://europepmc.org/article/MED/42530676> — claims: C094
- **E_MED_42608321** (pubmed) Retatrutide-Associated Improvements in Cardiovascular Risk Biomarkers in Adults With Obesity With or Without Type 2 Diabetes. <https://europepmc.org/article/MED/42608321> — claims: C085
- **E_MED_42611392** (pubmed) State-Level Prevalence of Obesity/overweight and Pancreatic Cancer Incidence in the United States: An Ecological Analysis Using BRFSS, CDC WONDER and ACS for the Year 2021. <https://europepmc.org/article/MED/42611392> — claims: C126
- **E_MED_42630988** (pubmed) Comparative effects of semaglutide tirzepatide and retatrutide on renal fibrosis in UUO and aged mice. <https://europepmc.org/article/MED/42630988> — claims: C113
- **E_MED_42669023** (pubmed) Online-Sourced Retatrutide Complicating Impending Diabetic Ketoacidosis in a Patient With Type 1 Diabetes and Concurrent Shigella Gastroenteritis. <https://europepmc.org/article/MED/42669023> — claims: C082, C083
- **E_MED_42688617** (pubmed) Comparative efficacy and safety of glucagon-like peptide 1 based drugs for weight loss in adults with overweight or obesity without diabetes: network meta-analysis of randomised controlled trials. <https://europepmc.org/article/MED/42688617> — claims: C097
- **E_MED_42744908** (pubmed) Cagrilintide and retatrutide combination therapy enhances weight loss and metabolic outcomes in obese male rats. <https://europepmc.org/article/MED/42744908> — claims: C103, C104
- **E_MED_42751099** (pubmed) Sustained weight loss exceeding 100 kg with sequential incretin-based therapy in Prader-Willi syndrome. <https://europepmc.org/article/MED/42751099> — claims: C095
- **E_MED_42792699** (pubmed) Potential Role of the Triple Receptor Agonist Retatrutide in Antipsychotic-Associated Metabolic Dysfunction Among Clozapine- and Olanzapine-Treated Schizophrenia Spectrum Disorders: A Narrative Review and Theoretical Framework. <https://europepmc.org/article/MED/42792699> — claims: C080, C081
- **E_MED_42810372** (pubmed) Retatrutide in adults with obesity and type 2 diabetes (TRIUMPH-2): a double-blind, parallel-group, randomised, placebo-controlled, phase 3 trial. <https://europepmc.org/article/MED/42810372> — claims: C089
- **E_MED_42814954** (pubmed) Retatrutide, a Triple Hormone Receptor Agonist, for Treatment of Obesity. <https://europepmc.org/article/MED/42814954> — claims: C090, C092
- **E_NCT06039826** (nct) A Phase 1 Study to Investigate the Effect of LY3437943 on the Pharmacokinetics of the Combined Oral Contraceptive Ethinyl Estradiol and Drospirenone in Female Participants <https://clinicaltrials.gov/study/NCT06039826> — claims: —
- **E_NCT06383390** (nct) A Phase 3, Randomized, Double-Blind, Placebo-Controlled, Event-Driven Study to Investigate the Effect of Retatrutide on the Incidence of Major Adverse Cardiovascular Events and Major Adverse Kidney Events in Participants With Body Mass Index ≥27 kg/m2 and Atherosclerotic Cardiovascular Disease and/or Chronic Kidney Disease <https://clinicaltrials.gov/study/NCT06383390> — claims: C064
- **E_OT_assoc_ENSG00000010310_MONDO_0005139** (opentargets) Open Targets association: GIPR and morbid obesity <https://platform.opentargets.org/evidence/ENSG00000010310/MONDO_0005139> — claims: C141
- **E_OT_assoc_ENSG00000010310_MONDO_0011122** (opentargets) Open Targets association: GIPR and obesity disorder <https://platform.opentargets.org/evidence/ENSG00000010310/MONDO_0011122> — claims: C140
- **E_OT_assoc_ENSG00000112164_MONDO_0005139** (opentargets) Open Targets association: GLP1R and morbid obesity <https://platform.opentargets.org/evidence/ENSG00000112164/MONDO_0005139> — claims: C137
- **E_OT_assoc_ENSG00000112164_MONDO_0011122** (opentargets) Open Targets association: GLP1R and obesity disorder <https://platform.opentargets.org/evidence/ENSG00000112164/MONDO_0011122> — claims: C136
- **E_OT_assoc_ENSG00000215644_MONDO_0011122** (opentargets) Open Targets association: GCGR and obesity disorder <https://platform.opentargets.org/evidence/ENSG00000215644/MONDO_0011122> — claims: C134
- **E_OT_drug_CHEMBL5095485** (opentargets) Open Targets drug profile: RETATRUTIDE <https://platform.opentargets.org/drug/CHEMBL5095485> — claims: C130, C131, C132
- **E_OT_target_ENSG00000010310** (opentargets) Open Targets target profile: GIPR <https://platform.opentargets.org/target/ENSG00000010310> — claims: C138, C139
- **E_OT_target_ENSG00000112164** (opentargets) Open Targets target profile: GLP1R <https://platform.opentargets.org/target/ENSG00000112164> — claims: C135
- **E_OT_target_ENSG00000215644** (opentargets) Open Targets target profile: GCGR <https://platform.opentargets.org/target/ENSG00000215644> — claims: C133
- **E_SEC_59478** (sec_filings) SEC EDGAR financials: ELI LILLY & Co <https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000059478> — claims: —

## Automatic checks

- claim dropped (numbers ['27'] are in the record, but not in the claim quote or in meta): The trial requires a BMI of at least 30 kg/m2 or at least 27 kg/m2 with a weight
- claim dropped (noise: narrow subgroup/risk association/caregiver criteria): Patients with a personal or family history of medullary thyroid carcinoma or mul
- claim dropped (noise: narrow subgroup/risk association/caregiver criteria): Patients with a personal or family history of medullary thyroid carcinoma or MEN
- claim dropped (numbers ['27'] are in the record, but not in the claim quote or in meta): A key inclusion criterion for the TRIUMPH-1 trial is a BMI ≥30.0 kg/m², or ≥27.0
- claim dropped (numbers ['27', '40'] are in the record, but not in the claim quote or in meta): Participants in trial NCT05548231 are native Chinese males or females aged 20 to
- claim dropped (noise: single case in a cohort without comparison to a control): Two participants in the 12 mg LY3437943 (2 mg) group discontinued the study due 
- claim dropped (noise: narrow subgroup/risk association/caregiver criteria): Retatrutide has an extended plasma detection window of approximately 56 days aft
- claim dropped (noise: narrow subgroup/risk association/caregiver criteria): Clinical obesity in US adults was associated with a 1.46 hazard ratio for all-ca
- claim dropped (numbers ['40', '64'] are in the record, but not in the claim quote or in meta): Combined overweight and obesity prevalence among US midlife women aged 40-64 yea
- claim dropped (quote not found in the record): The age-standardized prevalence of clinical obesity in US adults nearly doubled 
- claim dropped (noise: narrow subgroup/risk association/caregiver criteria): In a cross-sectional analysis of US adults from 2003-2004 and 2011-2014, higher 
- claim dropped (noise: narrow subgroup/risk association/caregiver criteria): In 2021, high BMI globally contributed to 5255 thyroid cancer-related deaths.
- claim dropped (noise: quote is a long list of names, not a statement): The FDA label for Orforglipron mentions the term obesity or weight management, b
- Scientific thesis: [E] downgraded to [AI] — evidence type (genetic/clinical/literature) for the Open Targets score is named, but the cited claims do not give such a score with these numbers: The glucagon, GLP-1, and GIP receptors are each associated with obesit
- Scientific thesis: [E] downgraded to [AI] — combines biology/PK and clinical data: Evidence regarding retatrutide in humans is limited to a single case r
- Commercial opportunity: [E] downgraded to [AI] — in commercial, numbers from different records in one [E] (they may be different measures): The prevalence of obesity in the United States remains high, with repo
- Commercial opportunity: [E] based only on study inclusion criteria (not a market indicator) dropped: Clinical trials for retatrutide are currently investigating population
- Commercial opportunity: [E] downgraded to [AI] — numbers ['100000'] absent from the cited claims (a calculation, not a fact): There are numerous competing obesity programs in Phase 3 development, 
- Clinical development plan: code added key efficacy results C097, C054 (no section cited them)
- Coverage: claim C078 (supports, clinical) not used in any section: In subjects with obesity, retatrutide treatment resulted in weight loss of up to
- Coverage: claim C086 (supports, clinical) not used in any section: A meta-analysis indicated that retatrutide treatment was linked to a weight loss
- Coverage: claim C088 (supports, clinical) not used in any section: Retatrutide 9 mg and 12 mg demonstrated superior bodyweight reduction compared t
- Coverage: claim C091 (supports, clinical) not used in any section: Retatrutide reduced pain scores in obese participants with knee osteoarthritis i
- Coverage: claim C099 (supports, clinical) not used in any section: Retatrutide significantly increased MASH resolution or histological improvement 
- Coverage: claim C102 (supports, safety_or_failure) not used in any section: Retatrutide safety profile in analyzed clinical trials was comparable to the pla
- Coverage: claim C109 (supports, clinical) not used in any section: Phase II trials of retatrutide in obesity have shown up to 24% body weight reduc
- Coverage: claim C111 (supports, mechanism) not used in any section: In pre-clinical cancer models, retatrutide reduced pancreatic cancer engraftment
- Coverage: claim C112 (supports, mechanism) not used in any section: Retatrutide treatment in pre-clinical lung cancer models reduced tumor engraftme
- Coverage: claim C117 (supports, clinical) not used in any section: Retatrutide demonstrates dose-dependent weight loss and improvements in glycemic
- Coverage: claim C121 (supports, clinical) not used in any section: Early clinical data for retatrutide indicate potential hepatoprotective effects 
- Conflicts: "Clinical safety profile and trial discontinuation" — status resolved downgraded to unresolved (the sides come from different studies)
- Capital: NCT07629401 skipped — phase not given in the registry
- Triage: C087 is not about the target drug — assessment dropped
- Triage: C110 is not about the target drug — assessment dropped
- Recommendation: [E] downgraded to [AI] — in the recommendation a fact must rest on a single claim: The sponsor reported four cases of serious drug-induced liver injury, 
- Recommendation: code added critical finding X001 (drug-related death, found by: model+keywords) — the model did not cite it
- Recommendation: code added critical finding X003 (critical finding, found by: model) — the model did not cite it
- Recommendation: code added counter-argument C089 from an unresolved contradiction "Clinical safety profile and trial discontinuation" — the recommendation cannot bypass it
- Critical findings rule (X001 (model+keywords); X002 (model+keywords); X003 (model)): without the findings the model would give "Invest", with them — "Do Not Invest" (rule applied by the model).
