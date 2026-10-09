"""ClinicalTrials.gov API v2."""

from .base import DataGetter, Query, get_json

URL = "https://clinicaltrials.gov/api/v2/studies"
MAX_PAGES = 20
SYNONYMS = {"retatrutide": ["LY3437943"]}


class ClinicalTrialsGetter(DataGetter):
    name = "clinicaltrials"

    def fetch(self, query: Query) -> list[dict]:
        params = {"pageSize": 100, "countTotal": "true", "format": "json"}
        if query.indication:
            params["query.cond"] = query.indication
        if query.mechanism:
            names = [query.mechanism] + SYNONYMS.get(query.mechanism.lower(), [])
            params["query.intr"] = " OR ".join(names)
        if len(params) == 3:
            return []

        records = []
        for _ in range(MAX_PAGES):
            data = get_json(URL, params)
            for study in data.get("studies", []):
                rec = self._to_evidence(study)
                if rec:
                    records.append(rec)
            token = data.get("nextPageToken")
            if not token:
                break
            params["pageToken"] = token
        return records

    @staticmethod
    def _to_evidence(study: dict) -> dict | None:
        proto = study.get("protocolSection", {})
        ident = proto.get("identificationModule", {})
        nct = ident.get("nctId")
        if not nct:
            return None

        status = proto.get("statusModule", {})
        design = proto.get("designModule", {})
        arms = proto.get("armsInterventionsModule", {})
        outcomes = proto.get("outcomesModule", {})

        return {
            "id": f"E_{nct}",
            "source_type": "nct",
            "source_id": nct,
            "url": f"https://clinicaltrials.gov/study/{nct}",
            "title": ident.get("officialTitle") or ident.get("briefTitle", ""),
            "text": proto.get("descriptionModule", {}).get("briefSummary", ""),
            "meta": {
                "status": status.get("overallStatus"),
                "why_stopped": status.get("whyStopped"),
                "start_date": status.get("startDateStruct", {}).get("date"),
                "primary_completion": status.get("primaryCompletionDateStruct", {}).get("date"),
                "completion": status.get("completionDateStruct", {}).get("date"),
                "phases": design.get("phases", []),
                "enrollment": design.get("enrollmentInfo", {}).get("count"),
                "conditions": proto.get("conditionsModule", {}).get("conditions", []),
                "interventions": [i.get("name") for i in arms.get("interventions", [])],
                "primary_outcomes": [
                    o.get("measure", "") for o in outcomes.get("primaryOutcomes", [])[:3]
                ],
                "lead_sponsor": proto.get("sponsorCollaboratorsModule", {})
                .get("leadSponsor", {})
                .get("name"),
                "has_results": study.get("hasResults", False),
            },
        }