# Investment Underwriting Report: tolebrutinib in multiple sclerosis

*Generated: 2026-10-10 21:17:15. Claims used: 133. Run cost: ~$0.0184.*

Legend: **[E]** = restates evidence, **[AI]** = AI inference. Ids in brackets are claim ids; every claim with its exact quote is in `report_tolebrutinib_claims.md`.

## 1. Recommendation: Do Not Invest

> 🚩 **Critical-finding rule.** A separate severity review (a model call, with a keyword backstop) rated these findings as able to stop the programme on their own:
> - C069 (found by model) [failed_pivotal_trial]: The failure to show meaningful benefit in a pivotal trial for a specific indication is a critical efficacy failure.
> - C071 (found by model) [death_or_life_threatening_harm]: Hy's Law criteria indicate the potential for drug-induced liver injury, which is a major, life-threatening safety risk.
> - C074 (found by model) [failed_pivotal_trial]: Failure of a pivotal trial to meet its expected efficacy objectives represents a significant threat to the drug's approval.
>
> Policy: a critical finding that stops the programme (death, regulatory halt, termination, failed pivotal trial, invalid key result) gives Do Not Invest; any other critical finding lowers the recommendation by one level. The model applied the rule itself and recommended **Do Not Invest**; the code only checked it.

- **[E]** In the HERCULES trial, tolebrutinib 60 mg reduced the risk of 6-month confirmed disability progression compared to placebo (HR 0.693, 95% CI 0.546 to 0.88, p = 0.0026). _[C011]_
- **[E]** Tolebrutinib showed no meaningful benefit in the PERSEUS trial for primary progressive multiple sclerosis. _[C069]_
- **[E]** Six participants in the tolebrutinib clinical program met Hy's Law criteria for potential serious liver injury. _[C071]_
- **[E]** The PERSEUS trial evaluating tolebrutinib in primary progressive multiple sclerosis failed to demonstrate the expected efficacy. _[C074]_
- **[AI]** The tolebrutinib clinical program is fundamentally compromised by the failure of the PERSEUS trial to demonstrate efficacy in primary progressive multiple sclerosis and the identification of six participants meeting Hy's Law criteria for potential serious liver injury. _[C069, C071, C074]_
- **[AI]** The safety profile is concerning, with 4.7% of participants experiencing ALT elevations greater than 3 times the upper limit of normal and an overall association with serious hepatic toxicity. _[C070, C075]_
- **[AI]** The inconsistent results across progressive multiple sclerosis subtypes indicate that the therapeutic window and patient selection for tolebrutinib remain poorly defined. _[C069, C074, C011]_

## 2. Scientific thesis

- **[E]** Tolebrutinib is a small molecule, oral, and CNS-penetrant irreversible inhibitor of Bruton's tyrosine kinase (BTK). _[C113, C131]_
- **[E]** BTK is a non-receptor tyrosine kinase required for B lymphocyte signaling, development, and differentiation. _[C132]_
- **[E]** BTK inhibitors modulate the activation of myeloid cells through Toll-like receptor and Fc receptor-dependent pathways. _[C083]_
- **[AI]** As an inference, the CNS-penetrant nature of tolebrutinib may allow it to address compartmentalized inflammation and smoldering disease biology in multiple sclerosis, which are processes often inaccessible to peripheral-acting therapies. _[C085, C103, C113]_
- **[E]** Human clinical trial data indicate that BTK inhibitors reduce MRI activity and the annualized relapse rate in multiple sclerosis patients compared to controls. _[C078, C079]_
- **[AI]** Inference from clinical data suggests that BTK inhibitors may provide a benefit in disability outcomes, as they have shown a reduced risk of 3-month confirmed disability worsening when compared to teriflunomide. _[C100]_

_Gaps in the data:_ The claims do not specify which experimental animal models, if any, were used to validate the efficacy of tolebrutinib in CNS disease.; Specific genetic evidence linking BTK directly to the pathogenesis of multiple sclerosis is not provided in the source material, and one source notes that multiple sclerosis is not among the top 100 diseases associated with BTK in the Open Targets database.; The clinical data regarding relapse and disability outcomes refer to the general class of BTK inhibitors, rather than specifying tolebrutinib-specific performance in these metrics.

## 3. Human translation thesis

- **[E]** Pharmacokinetic data from a 60 mg dose group indicates that tolebrutinib is rapidly absorbed, with mean Cmax values ranging from 9.94 ng/mL to 12.0 ng/mL and mean Tmax values ranging from 1.28 to 1.42 hours. _[C017, C018, C037, C038]_
- **[E]** The AUC0-24 for the 60 mg dose group was reported as 29.6 ng*h/mL and 30.5 ng*h/mL in available pharmacokinetic data. _[C019, C039]_
- **[E]** Tolebrutinib has a rapid half-life of approximately 2 hours in humans. _[C108]_
- **[E]** In a clinical study, tolebrutinib demonstrated cerebrospinal fluid (CSF) exposure 2 hours after a single 120 mg dose. _[C109]_
- **[AI]** It is an inference that tolebrutinib reaches the target in humans based on its classification as a brain-penetrant BTK inhibitor, though direct human target engagement data is not provided in these claims. _[C076, C087, C093, C113]_
- **[AI]** While non-human primate studies suggest tolebrutinib achieves CNS exposure levels exceeding its IC90, there is no human-specific data in the provided claims linking exposure levels to biological effect, clinical biomarkers, or demonstrated target engagement. _[C105, C110]_

_Gaps in the data:_ No human data provided linking specific tolebrutinib plasma or CSF exposure levels to clinical target engagement (e.g., occupancy of BTK in human immune cells).; Lack of human-specific pharmacodynamic data or biomarker response correlating with dose or exposure.; Sample sizes for the cited pharmacokinetic studies are not provided.

## 4. Clinical development plan

- **[E]** The clinical development program for tolebrutinib spans multiple sclerosis populations, including Phase 3 trials in non-relapsing secondary progressive multiple sclerosis (HERCULES), primary progressive multiple sclerosis (PERSEUS), and relapsing forms of multiple sclerosis (GEMINI 1 and 2). _[C010, C020, C028, C040]_
- **[AI]** In the HERCULES trial, tolebrutinib 60 mg demonstrated a reduction in the risk of 6-month confirmed disability progression compared to placebo (HR 0.693; 95% CI 0.546 to 0.88; p = 0.0026), though it did not show benefit on the upper-limb endpoint. _[C011, C073]_
- **[E]** In the GEMINI 1 and 2 trials, tolebrutinib 60 mg showed no significant difference in annualized relapse rates when compared to teriflunomide 14 mg. _[C029, C030, C041, C042, C101]_
- **[E]** The PERSEUS trial evaluating tolebrutinib in primary progressive multiple sclerosis did not demonstrate the expected efficacy or show meaningful clinical benefit. _[C069, C074]_
- **[AI]** Regarding regulatory status, tolebrutinib was approved in the United Arab Emirates in August 2025 for non-relapsing secondary progressive multiple sclerosis, and no FDA-approved drug label was found in openFDA. _[C088, C130]_
- **[AI]** As an inference, the inconsistent performance across different multiple sclerosis subtypes—specifically the failure to meet endpoints in primary progressive disease—suggests the program must clarify the specific patient populations where tolebrutinib provides a clinically meaningful benefit. _[C069, C074]_

_Gaps in the data:_ Comprehensive safety data for the Phase 3 trials are not covered by the claims of this section.; The specific criteria for defining 'meaningful benefit' or 'expected efficacy' beyond the cited disability and relapse endpoints are not provided.; Details on the long-term safety and tolerability trial enrollment status and results are not fully provided.

## 5. Competitive landscape

- **[E]** Tolebrutinib is a second-generation BTK inhibitor currently being developed for multiple sclerosis. _[C082]_
- **[E]** Clinical trials for tolebrutinib, such as GEMINI 1 and GEMINI 2, utilize teriflunomide as an active comparator. _[C002, C031, C043, C050]_
- **[E]** Tolebrutinib is also being evaluated against continued anti-CD20 therapy in clinical studies. _[C005]_
- **[E]** Several other BTK inhibitors are in development for multiple sclerosis, including evobrutinib, fenebrutinib, and remibrutinib. _[C061, C063, C092, C106, C107, C111, C112, C117]_
- **[AI]** As an inference, tolebrutinib faces competition from both established therapies used as active comparators and other pipeline BTK inhibitors currently in Phase 3 development. _[C002, C031, C043, C061, C063, C102, C106, C107]_
- **[AI]** As an inference, the clinical program for tolebrutinib seeks to address disability accumulation independent of relapses, which is identified as an unmet need in multiple sclerosis. _[C084, C086, C099]_

_Gaps in the data:_ Specific claims regarding the clinical differentiation of tolebrutinib from other BTK inhibitors or active comparators are not provided.; No claim provides a direct head-to-head efficacy comparison between tolebrutinib and other active agents.; The regulatory status of tolebrutinib in major markets like the US or EU is not fully covered, other than noting no FDA-approved label was found.

## 6. Commercial opportunity

- **[E]** Multiple sclerosis affects approximately 3.1 million people worldwide, with global prevalence rising to 38.1 per 100,000 people as of 2024. _[C121]_
- **[E]** The disease is a major cause of neurological disability in young adults, and disability accounts for 71.2% of the total disability-adjusted life years associated with the condition in some regions. _[C124, C129]_
- **[E]** A key unmet need is the progression of disability independent of relapse activity, particularly in non-relapsing secondary progressive multiple sclerosis, for which no treatments are currently approved. _[C084, C086, C099]_
- **[E]** Tolebrutinib is a second-generation BTK inhibitor currently in development for multiple sclerosis and has received approval in the United Arab Emirates for non-relapsing secondary progressive multiple sclerosis as of August 2025. _[C082, C088]_
- **[AI]** As an inference, the approval of tolebrutinib for non-relapsing secondary progressive multiple sclerosis addresses a significant clinical gap, as there are no FDA-approved treatments for this specific indication. _[C088, C099, C130]_
- **[E]** The competitive landscape is crowded with multiple Phase 3 programs for various therapies, including other BTK inhibitors like evobrutinib, fenebrutinib, and remibrutinib. _[C061, C063, C106, C107, C117]_

_Gaps in the data:_ Market size in monetary terms is not estimable from the provided claims.; Data comparing tolebrutinib's efficacy or safety directly against other BTK inhibitors or existing standards of care in head-to-head clinical trials are not provided.; The specific mechanism or comparative clinical advantage of tolebrutinib over established anti-CD20 therapies or other competing agents is not detailed.

## 7. Capital to next milestone

- **[AI]** Next milestone (AI inference from registry status): regulatory submission (some Phase 3 trials have already finished or reported); no Phase 3 trial is enrolling any more, so remaining spend is follow-up and data readout of trials with closed enrollment, plus the filing. _[E_AACT_NCT04410978, E_AACT_NCT04410991, E_AACT_NCT04411641, E_AACT_NCT04458051, E_AACT_NCT06372145]_
- **[E]** Lead sponsor(s) of the Phase 3 trials according to the registry: Sanofi. _[E_AACT_NCT04410978, E_AACT_NCT04410991, E_AACT_NCT04411641, E_AACT_NCT04458051, E_AACT_NCT06372145]_
- **[E]** Phase 3 trials excluded because they are completed or have results: NCT04410978, NCT04410991, NCT04411641, NCT04458051, NCT06372145. _[E_AACT_NCT04410978, E_AACT_NCT04410991, E_AACT_NCT04411641, E_AACT_NCT04458051, E_AACT_NCT06372145]_
- **[AI]** No Phase 3 trial with a known size is in progress, so the remaining trial spend cannot be computed from the registry (it has no cost or progress data). _[no claims]_
- **[E]** Sponsor funding (SEC EDGAR, company-wide, not specific to this drug) for Sanofi (SNY) [registry lead sponsor: Sanofi]: cash and cash equivalents EUR 7,657,000,000 as of 2025-12-31; R&D expense EUR 7,842,000,000 for the fiscal year ended 2025-12-31; net operating cash flow EUR 10,750,000,000 for the fiscal year ended 2025-12-31. _[E_SEC_1121404]_
- **[AI]** Limit of the estimate: Trial status and enrollment are a snapshot of the registry at the time of the search. _[no claims]_
- **[AI]** Limit of the estimate: Cost per participant is an assumed range for the therapeutic area (not from the sources); the share of cost already spent is estimated from elapsed time, not from real progress; real costs differ by trial design, country and duration. _[no claims]_

## 8. Catalyst calendar

- **[E]** Next expected data from the registry: NCT06372145 (Phase 3, ACTIVE_NOT_RECRUITING) primary completion 2029-04-30; primary endpoint: Number of Participants with Adverse Events (AEs) and Serious Adverse Events (SAEs), Adverse Events of Special Interest (AESIs) and AEs leading to permanent study intervention discontinuation. Dates come from the registry and can move. _[E_AACT_NCT06372145]_
- **[AI]** Competitor Phase 3 programmes with registry dates are listed in the table below; they show when the competitive picture may change, not whose drug is better. _[no claims]_
- **[AI]** Not predicted: regulatory filing and approval dates, and results of trials that are not in the registry. Registry dates are the sponsor's own estimates. _[no claims]_

| Date | Event | Trial | Phase | Status | Sponsor | Primary endpoint / programme |
|---|---|---|---|---|---|---|
| 2023-06-15 | Primary completion passed, results posted in the registry (this drug) | NCT04742400 | Phase 2 | UNKNOWN | National Institute of Neurological Disorders and Stroke (NINDS) | Disappearance of Paramagnetic Rim Lesions at 48 Weeks of 60 mg of Tolebrutinib. |
| 2024-07-15 | Primary completion passed, results posted in the registry (this drug) | NCT04410978 | Phase 3 | COMPLETED | Sanofi | Annualized Relapse Rate (ARR) as Assessed by Confirmed Protocol-defined Adjudicated Relaps |
| 2024-07-16 | Primary completion passed, results posted in the registry (this drug) | NCT04410991 | Phase 3 | COMPLETED | Sanofi | Annualized Relapse Rate (ARR) as Assessed by Confirmed Protocol-defined Adjudicated Relaps |
| 2024-08-29 | Primary completion passed, results posted in the registry (this drug) | NCT04411641 | Phase 3 | COMPLETED | Sanofi | Time to Onset of 6-Month Confirmed Disability Progression (CDP) as Assessed by Expanded Di |
| 2024-11-26 | Primary completion passed, results posted in the registry (this drug) | NCT03996291 | Phase 2 | COMPLETED | Sanofi | Number of Participants With Treatment-emergent Adverse Events (TEAEs) and Treatment-emerge |
| 2025-11-14 | Primary completion passed, results reported in the literature (this drug) | NCT04458051 | Phase 3 | COMPLETED | Sanofi | 6-month composite Confirmed Disability Progression (cCDP) |
| 2026-10-31 | Competitor Phase 3 programme: earliest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 2; RECRUITING 2 | TG Therapeutics, Inc. | ublituximab (4 trials) |
| 2026-11-01 | Competitor Phase 3 programme: earliest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 2 | Immunic AG | imu-838 (2 trials) |
| 2026-11-01 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 2 | Immunic AG | imu-838 (2 trials) |
| 2027-05-01 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | RECRUITING 1; ACTIVE_NOT_RECRUITING 2 | Amsterdam UMC, location VUmc; Haukeland University Hospital; Copenhagen University Hospital, Rigshospitalet | rituximab (3 trials) |
| 2027-05-06 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 5 | Hoffmann-La Roche; Novartis Pharmaceuticals; Sanofi | teriflunomide (5 trials) |
| 2027-05-06 | Competitor Phase 3 programme: earliest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 2; RECRUITING 1 | Sanofi | frexalimab (3 trials) |
| 2027-05-06 | Competitor Phase 3 programme: earliest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 2 | Sanofi | mri contrast-enhancing agents (2 trials) |
| 2027-12-01 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 3; RECRUITING 1 | Hoffmann-La Roche; Oculis; Copenhagen University Hospital, Rigshospitalet | methylprednisolone (4 trials) |
| 2028-03-24 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 2; RECRUITING 1 | Sanofi | frexalimab (3 trials) |
| 2028-03-24 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 2 | Sanofi | mri contrast-enhancing agents (2 trials) |
| 2028-09-30 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 2 | Novartis Pharmaceuticals | ofatumumab (2 trials) |
| 2029-04-30 | Expected primary data (primary completion) (this drug) | NCT06372145 | Phase 3 | ACTIVE_NOT_RECRUITING | Sanofi | Number of Participants with Adverse Events (AEs) and Serious Adverse Events (SAEs), Advers |
| 2029-12-31 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | RECRUITING 3; ACTIVE_NOT_RECRUITING 12 | Hoffmann-La Roche; Haukeland University Hospital; Novartis Pharmaceuticals | ocrelizumab (15 trials) |
| 2030-12-03 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 2; RECRUITING 1 | Novartis Pharmaceuticals | remibrutinib (3 trials) |
| 2032-05-31 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | ACTIVE_NOT_RECRUITING 2; RECRUITING 2 | TG Therapeutics, Inc. | ublituximab (4 trials) |
| 2034-07-28 | Competitor Phase 3 programme: latest primary completion (competitor) | — | Phase 3 | NOT_YET_RECRUITING 1; ACTIVE_NOT_RECRUITING 3; RECRUITING 2 | Novartis Pharmaceuticals; Biogen; Hoffmann-La Roche | fingolimod (6 trials) |

## 9. Probability of success (benchmark)

- **[AI]** ASSUMPTION from a published benchmark (All indications), not from the drug's own data: the highest phase in the registry is Phase 3, and the average programme at this stage reaches approval about 52% of the time. If the pivotal Phase 3 is positive the benchmark for approval rises to about 91% (NDA/BLA to approval); if it fails the programme stops. _[E_AACT_NCT03996291, E_AACT_NCT04410978, E_AACT_NCT04410991, E_AACT_NCT04411641, E_AACT_NCT04458051, E_AACT_NCT04742400, E_AACT_NCT06064539, E_AACT_NCT06106074, E_AACT_NCT06372145]_
- **[AI]** Phase 3 results already reported (registry or literature) for: NCT04410978, NCT04410991, NCT04411641, NCT04458051, NCT06372145. The benchmark does not know them: read the efficacy and safety sections to judge whether this asset is above or below the average. _[E_AACT_NCT03996291, E_AACT_NCT04410978, E_AACT_NCT04410991, E_AACT_NCT04411641, E_AACT_NCT04458051, E_AACT_NCT04742400, E_AACT_NCT06064539, E_AACT_NCT06106074, E_AACT_NCT06372145]_
- **[AI]** The benchmark is an average over many programmes and is not adjusted for this asset's data, class or sponsor; the asset-specific evidence is in the other sections. Critical findings are present (C069, C071, C074): treat the benchmark as an upper bound. _[no claims]_

| Benchmark | Phase 1→2 | Phase 2→3 | Phase 3→NDA/BLA | NDA/BLA→approval | PoS to approval from current stage |
|---|---|---|---|---|---|
| All indications | 52.0% | 28.9% | 57.8% | 90.6% | **52%** |

Source: BIO, Informa Pharma Intelligence, QLS: Clinical Development Success Rates and Contributing Factors 2011-2020 (2021), https://go.bio.org/rs/490-EHZ-999/images/ClinicalDevelopmentSuccessRates2011_2020.pdf

## 10. Key risks

- **[E]** The PERSEUS trial failed to demonstrate expected efficacy in primary progressive multiple sclerosis, and the drug showed no meaningful benefit in this study. _[C069, C074]_
- **[E]** In the HERCULES trial, tolebrutinib did not demonstrate benefit on the upper-limb endpoint. _[C073]_
- **[E]** Clinical safety data indicates that 4.7% of tolebrutinib-exposed participants experienced ALT elevations greater than 3 times the upper limit of normal. _[C070]_
- **[E]** Six participants in the tolebrutinib clinical program met Hy’s Law criteria for potential serious liver injury, and the drug is associated with a risk of serious hepatic toxicity. _[C071, C075]_
- **[E]** In the HERCULES trial, 29 participants in the 60 mg treatment group discontinued the study due to adverse events. _[C016]_
- **[AI]** An inference can be drawn that the hepatotoxicity signals observed in preclinical human liver spheroids correlate with the serious hepatic toxicity and Hy's Law cases identified in clinical development. _[C071, C075, C115]_
- **[AI]** It is an inference that efficacy evaluations for tolebrutinib are weakened by the failure of major trials like PERSEUS and HERCULES, as well as the open-label, non-comparative design of long-term extension studies. _[C069, C073, C074, C095]_

_Gaps in the data:_ Total study population size for the HERCULES trial to contextualize the 29 discontinuations.; Specific details regarding the nature of the adverse events leading to discontinuation.; Information on any mitigation strategies or regulatory responses regarding the identified hepatic toxicity risks.

## 11. Contradictory evidence

- **Efficacy in progressive multiple sclerosis across trials** (unresolved; endpoint: Disability progression or disease benefit; comparator: placebo)  
  supports: C011, C098; contradicts: C069, C074  
  **[AI]** The conflict arises from divergent outcomes in two major phase 3 trials: the HERCULES trial showed benefit in nrSPMS, while the PERSEUS trial failed to demonstrate efficacy in primary progressive MS. Since these represent distinct clinical populations within the spectrum of progressive MS, both results can be empirically valid. The conflict is unresolved as the drug shows therapeutic promise in one specific population but failed in another.

## 12. Critical unknowns

- Definition of a safe therapeutic dose that avoids Hy's Law-level hepatotoxicity in a broad patient population.
- Identification of specific biomarkers or patient characteristics that predict therapeutic response versus liver toxicity risk.
- Regulatory path to approval given the failed efficacy in primary progressive MS and the significant safety signals.

## 13. Diligence questions

1. Can the company provide a detailed breakdown of the 6 cases of Hy's Law, including time-to-onset and potential confounding factors?
2. What specific mechanisms of hepatotoxicity are being investigated, and can they be mitigated by dose adjustment or monitoring?
3. How does the company reconcile the failure in the PERSEUS primary progressive MS trial with the results in non-relapsing secondary progressive MS?
4. Is there a post-hoc analysis planned or underway to identify responders in the failed clinical trials?
5. What is the status of the regulatory dialogue with the FDA regarding the hepatic safety signal?

## 14. What would change the conclusion

- A clear, regulator-approved risk mitigation strategy that allows for a safe re-introduction or continued use of tolebrutinib without the recurring serious hepatic safety signals.
- Compelling new clinical data from a randomized, controlled trial demonstrating a clear efficacy advantage over existing standards of care in a well-defined, safe population.
- A formal regulatory approval from a major health authority (FDA/EMA) for a specific multiple sclerosis indication.

## 15. Sources

- **E_AACT_NCT03996291** (nct_aact) Long-term Extension Safety and Efficacy Study of SAR442168 in Participants With Relapsing Multiple Sclerosis <https://clinicaltrials.gov/study/NCT03996291> — claims: —
- **E_AACT_NCT04410978** (nct_aact) A Phase 3, Randomized, Double-blind Efficacy and Safety Study Comparing SAR442168 to Teriflunomide (Aubagio®) in Participants With Relapsing Forms of Multiple Sclerosis <https://clinicaltrials.gov/study/NCT04410978> — claims: C028, C029, C030, C031
- **E_AACT_NCT04410978_pk** (nct_aact_pk) Pharmacokinetic results: Relapsing Forms of Multiple Sclerosis (RMS) Study of Bruton's Tyrosine Kinase (BTK) Inhibitor Tolebrutinib (SAR442168) (GEMINI 1) <https://clinicaltrials.gov/study/NCT04410978> — claims: C037, C038, C039
- **E_AACT_NCT04410991** (nct_aact) A Phase 3, Randomized, Double-blind Efficacy and Safety Study Comparing SAR442168 to Teriflunomide (Aubagio®) in Participants With Relapsing Forms of Multiple Sclerosis <https://clinicaltrials.gov/study/NCT04410991> — claims: C040, C041, C042, C043
- **E_AACT_NCT04410991_flow** (nct_aact_flow) Participant flow: Relapsing Forms of Multiple Sclerosis (RMS) Study of Bruton's Tyrosine Kinase (BTK) Inhibitor Tolebrutinib (SAR442168) (GEMINI 2) <https://clinicaltrials.gov/study/NCT04410991> — claims: C050
- **E_AACT_NCT04411641** (nct_aact) A Phase 3, Randomized, Double-blind, Efficacy and Safety Study Comparing SAR442168 to Placebo in Participants With Nonrelapsing Secondary Progressive Multiple Sclerosis <https://clinicaltrials.gov/study/NCT04411641> — claims: C010, C011
- **E_AACT_NCT04411641_flow** (nct_aact_flow) Participant flow: Nonrelapsing Secondary Progressive Multiple Sclerosis (NRSPMS) Study of Bruton's Tyrosine Kinase (BTK) Inhibitor Tolebrutinib (SAR442168) (HERCULES) <https://clinicaltrials.gov/study/NCT04411641> — claims: C016
- **E_AACT_NCT04411641_pk** (nct_aact_pk) Pharmacokinetic results: Nonrelapsing Secondary Progressive Multiple Sclerosis (NRSPMS) Study of Bruton's Tyrosine Kinase (BTK) Inhibitor Tolebrutinib (SAR442168) (HERCULES) <https://clinicaltrials.gov/study/NCT04411641> — claims: C017, C018, C019
- **E_AACT_NCT04458051** (nct_aact) A Phase 3, Randomized, Double-blind, Efficacy and Safety Study Comparing SAR442168 to Placebo in Participants With Primary Progressive Multiple Sclerosis (PERSEUS) <https://clinicaltrials.gov/study/NCT04458051> — claims: C020
- **E_AACT_NCT04742400** (nct_aact) A Phase 2 Clinical Trial of Tolebrutinib, a Brain-penetrant Bruton's Tyrosine Kinase Inhibitor, for the Modulation of Chronically Inflamed White Matter Lesions in Multiple Sclerosis <https://clinicaltrials.gov/study/NCT04742400> — claims: C005
- **E_AACT_NCT06064539** (nct_aact) A Phase 1, Single-center, Open-label, Two-cohort, Two-period, One-sequence, Two Treatment, Drug-drug Interaction Study of the Effects of Gemfibrozil and Rifampicin on SAR442168 in Healthy Subjects <https://clinicaltrials.gov/study/NCT06064539> — claims: —
- **E_AACT_NCT06106074** (nct_aact) A Randomized, Double-blind, Placebo-controlled Study of the Tolerability and Pharmacokinetics of Ascending Single and 14-day Repeated Oral Doses of SAR442168 With a Food Effect Investigation in Healthy Adult Participants <https://clinicaltrials.gov/study/NCT06106074> — claims: —
- **E_AACT_NCT06372145** (nct_aact) An Interventional, Phase 3 Extension Study to Investigate Long-term Safety and Tolerability of Tolebrutinib in Participants With Relapsing Multiple Sclerosis, Primary Progressive Multiple Sclerosis, or Nonrelapsing Secondary Progressive Multiple Sclerosis <https://clinicaltrials.gov/study/NCT06372145> — claims: C002
- **E_COMP_fenebrutinib** (competitor_registry) Competitor Phase 3 programme in multiple sclerosis: fenebrutinib <https://clinicaltrials.gov/search?cond=multiple+sclerosis&intr=fenebrutinib> — claims: C063
- **E_COMP_remibrutinib** (competitor_registry) Competitor Phase 3 programme in multiple sclerosis: remibrutinib <https://clinicaltrials.gov/search?cond=multiple+sclerosis&intr=remibrutinib> — claims: C061
- **E_FDA_absent_tolebrutinib** (openfda) openFDA drug label search: tolebrutinib <https://api.fda.gov/drug/label.json?search=openfda.generic_name%3A%22tolebrutinib%22+OR+openfda.brand_name%3A%22tolebrutinib%22+OR+openfda.substance_name%3A%22tolebrutinib%22&limit=10> — claims: C130
- **E_MED_34418400** (pubmed) Safety and efficacy of tolebrutinib, an oral brain-penetrant BTK inhibitor, in relapsing multiple sclerosis: a phase 2b, randomised, double-blind, placebo-controlled trial. <https://europepmc.org/article/MED/34418400> — claims: C113
- **E_MED_34724345** (pubmed) Phase 1 clinical trial evaluating safety, exposure and pharmacodynamics of BTK inhibitor tolebrutinib (PRN2246, SAR442168). <https://europepmc.org/article/MED/34724345> — claims: C108, C109
- **E_MED_36301434** (pubmed) Bruton's Tyrosine Kinase Inhibition in Multiple Sclerosis. <https://europepmc.org/article/MED/36301434> — claims: C117
- **E_MED_38965189** (pubmed) Comparative CNS Pharmacology of the Bruton's Tyrosine Kinase (BTK) Inhibitor Tolebrutinib Versus Other BTK Inhibitor Candidates for Treating Multiple Sclerosis. <https://europepmc.org/article/MED/38965189> — claims: C105, C106, C107
- **E_MED_40651461** (pubmed) Tolebrutinib for non-relapsing secondary progressive multiple sclerosis: a critical therapeutic gap. <https://europepmc.org/article/MED/40651461> — claims: C098, C099
- **E_MED_41015666** (pubmed) Multiple sclerosis updates and the safety and efficacy of Bruton tyrosine kinase inhibitors in it: A systematic review. <https://europepmc.org/article/MED/41015666> — claims: C092
- **E_MED_41284222** (pubmed) Tolebrutinib: First Approval. <https://europepmc.org/article/MED/41284222> — claims: C087, C088
- **E_MED_41518640** (pubmed) The Burden of Multiple Sclerosis in Japan from 1990 to 2021 and Predictions to 2050 Based on the Global Burden of Disease Study 2021. <https://europepmc.org/article/MED/41518640> — claims: C129
- **E_MED_41518815** (pubmed) Efficacy and safety of Bruton's tyrosine kinase inhibitors compared to Teriflunomide in relapsing multiple sclerosis: A systematic review and meta-analysis. <https://europepmc.org/article/MED/41518815> — claims: C100, C101, C102
- **E_MED_41650827** (pubmed) Global, regional, and national burden of multiple sclerosis from 1990 to 2021 and projections to 2040: A comprehensive analysis from the global burden of disease study. <https://europepmc.org/article/MED/41650827> — claims: C124
- **E_MED_41717535** (pubmed) Tolebrutinib Phase 2b Long-Term Extension Study: Two-Year Safety, MRI, and Clinical Efficacy Outcomes in Patients With Relapsing Multiple Sclerosis Patients. <https://europepmc.org/article/MED/41717535> — claims: C093, C095
- **E_MED_42075951** (pubmed) Bruton's Tyrosine Kinase Inhibitors in Multiple Sclerosis: Mechanistic Considerations Across Relapsing and Progressive Disease. <https://europepmc.org/article/MED/42075951> — claims: C082
- **E_MED_42126690** (pubmed) Bruton's Tyrosine Kinase Inhibitors in Multiple Sclerosis. <https://europepmc.org/article/MED/42126690> — claims: C076
- **E_MED_42352643** (pubmed) Emerging Role of BTK Inhibitors in Multiple Sclerosis: From Immunobiology to Clinical Translation. <https://europepmc.org/article/MED/42352643> — claims: C078, C079
- **E_MED_42418948** (pubmed) Mechanistically resolved prediction of compound hepatotoxicity using primary human liver spheroids-Application to recent real-world cases. <https://europepmc.org/article/MED/42418948> — claims: C115
- **E_MED_42462178** (pubmed) The Art of Sequencing Disease-Modifying Therapies in Multiple Sclerosis. <https://europepmc.org/article/MED/42462178> — claims: C103
- **E_MED_42482223** (pubmed) Targeting progressive multiple sclerosis: Toward mechanism-informed precision medicine. <https://europepmc.org/article/MED/42482223> — claims: C084, C085
- **E_MED_42518914** (pubmed) Targeting Bruton's Tyrosine Kinase (BTK) in Autoimmunity: Achievements, Opportunities and Challenges. <https://europepmc.org/article/MED/42518914> — claims: C083
- **E_MED_42546561** (pubmed) Tolebrutinib liver safety: A detailed overview. <https://europepmc.org/article/MED/42546561> — claims: C069, C070, C071
- **E_MED_42693747** (pubmed) Global prevalence of multiple sclerosis surpasses 3 million: 2024 update of the Multiple Sclerosis International Federation Atlas of MS. <https://europepmc.org/article/MED/42693747> — claims: C121
- **E_MED_42828703** (pubmed) Horizon Scanning of Multiple Sclerosis Expenditure in Italy (2025-2029): Updated Insights from the Oracle Model. <https://europepmc.org/article/MED/42828703> — claims: C086
- **E_OT_drug_CHEMBL4650323** (opentargets) Open Targets drug profile: TOLEBRUTINIB <https://platform.opentargets.org/drug/CHEMBL4650323> — claims: C131
- **E_OT_target_ENSG00000010671** (opentargets) Open Targets target profile: BTK <https://platform.opentargets.org/target/ENSG00000010671> — claims: C132
- **E_PPR_PPR1319404** (epmc_ppr) Non-Relapsing Secondary Progressive Multiple Sclerosis in the Tolebrutinib Era: Global Evidence and a Proposed Clinical Implementation Pathway for the Gulf Cooperation Council <https://europepmc.org/article/PPR/PPR1319404> — claims: C073, C074, C075
- **E_PPR_PPR828673** (epmc_ppr) Comparative CNS Pharmacology of the Bruton’s Tyrosine Kinase (BTK) Inhibitor Tolebrutinib Versus Other BTK Inhibitor Candidates for Treating Multiple Sclerosis <https://europepmc.org/article/PPR/PPR828673> — claims: C110, C111, C112
- **E_SEC_1121404** (sec_filings) SEC EDGAR financials: Sanofi <https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001121404> — claims: —

## Automatic checks

- claim dropped (numbers ['18', '20'] are in the record, but not in the claim quote or in meta): A Phase 2 clinical trial is investigating whether tolebrutinib can help clear in
- claim dropped (numbers ['48.9'] are in the record, but not in the claim quote or in meta): The study population consisted of participants between 18 and 60 years of age wi
- claim dropped (noise: narrow subgroup/risk association/caregiver criteria): The primary reasons for study discontinuation in the tolebrutinib 60 mg group we
- claim dropped (noise: narrow subgroup/risk association/caregiver criteria): The primary reasons for study discontinuation in the teriflunomide 14 mg group w
- claim dropped (numbers ['31'] from the claim are absent from the record): In Part A of the tolebrutinib Phase 2 trial, 17 out of 31 participants reported 
- claim dropped (numbers ['31'] from the claim are absent from the record): In Part A of the tolebrutinib Phase 2 trial, 20 out of 31 participants reported 
- claim dropped (noise: narrow subgroup/risk association/caregiver criteria): In the Tolebrutinib 5 mg group of trial NCT03996291, one participant did not com
- claim dropped (numbers ['60'] are in the record, but not in the claim quote or in meta): In 6 healthy volunteers, a 60-mg oral dose of tolebrutinib showed a 3.5-hour hal
- claim dropped (numbers ['130'] are in the record, but not in the claim quote or in meta): In a phase 2b trial of 130 participants with relapsing multiple sclerosis, toleb
- claim dropped (numbers ['65'] are in the record, but not in the claim quote or in meta): In the United States, the prevalence rate of multiple sclerosis among older adul
- claim dropped (noise: quote is a long list of names, not a statement): Several drugs appear in the FDA database search for labels mentioning multiple s
- Human translation thesis: statement about missing data -> [AI]: While non-human primate studies suggest tolebrutinib achieves CNS expo
- Clinical development plan: [E] downgraded to [AI] — combines claims with opposite directions: In the HERCULES trial, tolebrutinib 60 mg demonstrated a reduction in 
- Clinical development plan: statement about missing data -> [AI]: Regarding regulatory status, tolebrutinib was approved in the United A
- Commercial opportunity: statement about missing data -> [AI]: As an inference, the approval of tolebrutinib for non-relapsing second
- Coverage: claim C068 (supports, clinical) not used in any section: Tolebrutinib reduced disability progression by 31% in nrSPMS and 29% in RMS.
- Coverage: claim C072 (supports, clinical) not used in any section: The HERCULES trial of tolebrutinib in 1,131 participants showed a reduction in d
- Coverage: claim C077 (supports, clinical) not used in any section: Tolebrutinib showed a hazard ratio for confirmed disability worsening of 0.71 de
- Coverage: claim C089 (supports, clinical) not used in any section: Tolebrutinib demonstrated dose-dependent efficacy in reducing new Gd-enhancing l
- Coverage: claim C091 (supports, clinical) not used in any section: Tolebrutinib has been associated with disability slowing in patients with non-re
- Coverage: claim C094 (supports, clinical) not used in any section: In a long-term extension study of tolebrutinib, the annualized relapse rate on t
- Coverage: claim C098 (supports, clinical) not used in any section: Tolebrutinib reduced the risk of disability progression in non-relapsing seconda
- Coverage: claim C104 (supports, translation) not used in any section: In non-human primate studies, tolebrutinib demonstrated a higher rate of reactio
- Coverage: claim C114 (supports, clinical) not used in any section: The 60 mg dose of tolebrutinib was identified as the most efficacious in the pha
- Capital: Sanofi figures are not in USD — comparison was not performed
- Recommendation: [E] downgraded to [AI] — in the recommendation a fact must rest on a single claim: The safety profile is concerning, with 4.7% of participants experienci
- Recommendation: code added critical finding C069 (critical finding, found by: model) — the model did not cite it
- Recommendation: code added critical finding C071 (critical finding, found by: model) — the model did not cite it
- Recommendation: code added critical finding C074 (critical finding, found by: model) — the model did not cite it
- Critical findings rule (C069 (model); C071 (model); C074 (model)): without the findings the model would give "Conditional", with them — "Do Not Invest" (rule applied by the model).
