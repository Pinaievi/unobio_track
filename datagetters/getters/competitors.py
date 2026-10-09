"""Конкуренти: активні Phase 3 програми ІНШИХ препаратів у тому самому показанні.

Джерело: реєстр ClinicalTrials.gov (API v2). Це не докази ефективності, а карта
конкурентного поля: хто (препарат, спонсор) веде Phase 3 у цьому показанні, скільки
випробувань, скільки учасників, коли очікується завершення.

Один запис evidence = один препарат-конкурент (випробування згруповані за препаратом).
source_type = "competitor_registry". Він навмисно НЕ починається з "nct", тож розрахунок
капіталу (build_report.trial_table) ці випробування не бере: капітал рахуємо лише для
цільового препарату.

Без індикації (query.indication порожній) getter нічого не повертає.
"""

import re

from .base import DataGetter, Query, get_json

URL = "https://clinicaltrials.gov/api/v2/studies"
MAX_PAGES = 5
TOP_DRUGS = 12
STATUSES = "RECRUITING|ACTIVE_NOT_RECRUITING|NOT_YET_RECRUITING|ENROLLING_BY_INVITATION"
DRUG_TYPES = {"DRUG", "BIOLOGICAL", "COMBINATION_PRODUCT"}

SYNONYMS = {"retatrutide": ["ly3437943"]}

SKIP_RE = re.compile(
    r"(?i)placebo|sham|saline|standard of care|usual care|diet|exercise|lifestyle|"
    r"counsel|behaviou?r|surgery|bypass|sleeve|device|education|vehicle|matching|"
    r"best supportive|no intervention|control")


def drug_key(name: str) -> str:
    """'Semaglutide 2.4 mg subcutaneous' -> 'semaglutide'. Дози й форми прибираємо."""
    n = name.lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|ug|g|ml|iu|units?|%)\b", " ", n)
    n = re.sub(r"\b(?:subcutaneous|oral|injection|tablets?|capsules?|once|weekly|daily|"
               r"low|high|medium|dose|doses|arm|group|cohort|titration|escalation|"
               r"sc|po|qw|qd|solution|pen)\b", " ", n)
    n = re.sub(r"[^a-z0-9\- ]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


class CompetitorsGetter(DataGetter):
    name = "competitors"

    def fetch(self, query: Query) -> list[dict]:
        if not query.indication:
            return []
        target = (query.mechanism or "").lower().strip()
        own = {target, *SYNONYMS.get(target, [])} - {""}

        params = {"pageSize": 100, "format": "json",
                  "query.cond": query.indication,
                  "filter.advanced": "AREA[Phase]PHASE3",
                  "filter.overallStatus": STATUSES}
        studies = []
        for _ in range(MAX_PAGES):
            data = get_json(URL, params)
            studies += data.get("studies", [])
            token = data.get("nextPageToken")
            if not token:
                break
            params["pageToken"] = token
        return self._group(studies, own, query.indication)

    @staticmethod
    def _group(studies: list[dict], own: set, indication: str) -> list[dict]:
        drugs: dict[str, dict] = {}
        for st in studies:
            proto = st.get("protocolSection", {})
            nct = proto.get("identificationModule", {}).get("nctId")
            if not nct:
                continue
            arms = proto.get("armsInterventionsModule", {}).get("interventions", [])
            names = [i.get("name", "") for i in arms]
            blob = " ".join(names).lower() + " " + \
                proto.get("identificationModule", {}).get("officialTitle", "").lower()
            if any(o in blob for o in own):
                continue
            status = proto.get("statusModule", {})
            sponsor = proto.get("sponsorCollaboratorsModule", {}) \
                .get("leadSponsor", {}).get("name")
            enroll = proto.get("designModule", {}).get("enrollmentInfo", {}).get("count") or 0
            keys = set()
            for i in arms:
                nm = i.get("name", "")
                if i.get("type") not in DRUG_TYPES or SKIP_RE.search(nm):
                    continue
                k = drug_key(nm)
                if len(k) >= 4:
                    keys.add(k)
            for k in keys:
                d = drugs.setdefault(k, {"trials": {}, "sponsors": {}})
                d["trials"][nct] = {
                    "status": status.get("overallStatus"),
                    "enrollment": enroll,
                    "start": status.get("startDateStruct", {}).get("date"),
                    "primary_completion":
                        status.get("primaryCompletionDateStruct", {}).get("date"),
                }
                if sponsor:
                    d["sponsors"][sponsor] = d["sponsors"].get(sponsor, 0) + 1

        ranked = sorted(drugs.items(),
                        key=lambda kv: (-len(kv[1]["trials"]),
                                        -sum(t["enrollment"] for t in kv[1]["trials"].values())))
        out = []
        for k, d in ranked[:TOP_DRUGS]:
            trials = d["trials"]
            sponsors = sorted(d["sponsors"], key=lambda s: -d["sponsors"][s])
            total = sum(t["enrollment"] for t in trials.values())
            pcs = sorted(t["primary_completion"] for t in trials.values()
                         if t["primary_completion"])
            statuses = {}
            for t in trials.values():
                statuses[t["status"]] = statuses.get(t["status"], 0) + 1
            nct_list = sorted(trials)
            text = (
                f"Competitor program in {indication}: {k} has {len(trials)} registered "
                f"Phase 3 trial(s) in {indication} that are active or planned. "
                f"Lead sponsor(s): {', '.join(sponsors[:3]) or 'not stated'}. "
                f"Planned enrollment across these trials: {total} participants. "
                f"Statuses: {', '.join(f'{s} {n}' for s, n in sorted(statuses.items()))}. "
                + (f"Earliest planned primary completion {pcs[0]}, latest {pcs[-1]}. "
                   if pcs else "")
                + f"Trials: {', '.join(nct_list[:8])}. "
                "This is a registry snapshot of trial activity. A registered trial is "
                "not evidence that the drug works.")
            slug = re.sub(r"[^a-z0-9]+", "_", k).strip("_")
            out.append({
                "id": f"E_COMP_{slug}",
                "source_type": "competitor_registry",
                "source_id": slug,
                "url": "https://clinicaltrials.gov/search?cond="
                       + indication.replace(" ", "+") + f"&intr={k.replace(' ', '+')}",
                "title": f"Competitor Phase 3 programme in {indication}: {k}",
                "text": text,
                "meta": {"drug": k, "trials": len(trials), "enrollment_total": total,
                         "sponsors": sponsors[:3], "ncts": nct_list[:20],
                         "statuses": statuses,
                         "primary_completion_earliest": pcs[0] if pcs else None,
                         "primary_completion_latest": pcs[-1] if pcs else None},
            })
        return out