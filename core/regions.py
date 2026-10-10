"""Мітка регіону claim-а: США, Європа, обидва, інший, глобальний/невказаний.
Це лише інформаційна мітка (фільтр у Claims explorer і додаток claims); розділи звіту за
регіонами не ділимо, бо європейських джерел (EMA, реєстри ЄС) у нас немає.

Визначається КОДОМ за текстом claim і цитати та за типом джерела, без виклику LLM.
Це проста перевірна евристика, а не оцінка моделі: якщо в тексті прямо названо
країну чи агентство, регіон проставляється; інакше claim вважається «глобальним/невказаним».
"""
import re

US_RE = re.compile(
    r"(?i)\b(?:united states|u\.s\.a?\.?|usa|americans?|america|"
    r"fda|food and drug administration|nhanes|cdc|nchs|medicare|medicaid|"
    r"nih|us food|us adults?|us population)\b")
US_CASE_RE = re.compile(r"\bUS\b")          # «US» окремо, лише з великих літер
EU_RE = re.compile(
    r"(?i)\b(?:europe|european|ema|european medicines agency|eu|eea|united kingdom|"
    r"england|scotland|wales|germany|german|france|french|italy|italian|spain|spanish|"
    r"netherlands|dutch|sweden|swedish|denmark|danish|norway|norwegian|finland|finnish|"
    r"poland|polish|belgium|austria|switzerland|ireland|portugal|greece|czech|hungary|"
    r"mhra)\b")
UK_CASE_RE = re.compile(r"\b(?:UK|NICE)\b")      # лише великими літерами
OTHER_RE = re.compile(
    r"(?i)\b(?:china|chinese|japan|japanese|korea|korean|india|indian|taiwan|"
    r"australia|australian|canada|canadian|brazil|brazilian|asia|asian|"
    r"middle east|africa|african|latin america)\b")


def claim_region(claim: str, quote: str, source_type: str | None = None) -> str:
    """US / EU / US+EU / Other / Global для одного claim."""
    text = f"{claim} {quote}"
    us = bool(US_RE.search(text) or US_CASE_RE.search(text))
    eu = bool(EU_RE.search(text) or UK_CASE_RE.search(text))
    if source_type in ("openfda", "sec_filings"):    # мітки FDA і звітність SEC — це США
        us = True
    if us and eu:
        return "US+EU"
    if us:
        return "US"
    if eu:
        return "EU"
    if OTHER_RE.search(text):
        return "Other"
    return "Global"