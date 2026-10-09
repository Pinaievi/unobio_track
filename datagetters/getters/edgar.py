"""
getters/edgar.py — фінанси публічної компанії-спонсора з SEC EDGAR (XBRL).

Що збирає: один запис на компанію з останніми річними даними:
  - витрати на R&D за останній фінансовий рік;
  - грошові кошти та еквіваленти (остання звітна дата);
  - чистий операційний грошовий потік за рік (від'ємний = компанія «спалює» гроші).
Це загальні цифри компанії, а НЕ витрати на один препарат: у звіті так і сказано.

Як визначається компанія:
  1. SPONSORS — ручна таблиця «препарат -> тикер» (конфігурація, не докази). Перевір її.
  2. Якщо препарату в таблиці немає: повнотекстовий пошук EDGAR за назвою препарату,
     береться перша компанія, АЛЕ лише коли задано EDGAR_ALLOW_UNVERIFIED=1. Знайдена так
     компанія може бути конкурентом чи власником роялті, тому за замовчуванням ми цього
     не робимо (мовчання краще за хибну цифру). Тоді meta.sponsor_verified = False.
Компаній, що не подають звіти до SEC (наприклад, Roche), тут немає: це чесний пробіл.

ВАЖЛИВО: SEC вимагає в заголовку User-Agent ваше ім'я та e-mail. Задай змінну оточення
  SEC_USER_AGENT="Ім'я Прізвище email@example.com"
Без неї SEC може повертати 403.

Запуск окремо не потрібен: delegator.py знаходить цей файл сам.
"""

import hashlib
import json
import os
import re
import time

import requests

from .base import CACHE_DIR, DataGetter, Query

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
BROWSE_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik:010d}"


SPONSORS = {
    "retatrutide": "LLY",
    "lepodisiran": "LLY",
    "maridebart cafraglutide": "AMGN",
    "amycretin": "NVO",
    "zilebesiran": "ALNY",
    "mivelsiran": "ALNY",
    "sonelokimab": "MLTX",
    "efruxifermin": "AKRO",
    "frexalimab": "SNY",
    "duvakitug": "TEVA",
    "elironrasib": "RVMD",
    "zoldonrasib": "RVMD",
    "verekitug": "UPB",
    "navenibart": "ATXS",
    "kt-474": "KYMR",
    "hro761": "NVS",

    "trontinemab": None,    
    "divarasib": None,      
    "petrelintide": None,
}


TAGS = {
    "rd": [("us-gaap", "ResearchAndDevelopmentExpense"),
           ("us-gaap", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"),
           ("ifrs-full", "ResearchAndDevelopmentExpense")],
    "cash": [("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
             ("us-gaap", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
             ("ifrs-full", "CashAndCashEquivalents")],
    "opcf": [("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
             ("ifrs-full", "CashFlowsFromUsedInOperatingActivities")],
}
ANNUAL_FORMS = {"10-K", "20-F", "40-F", "10-K/A"}


def _headers() -> dict:
    ua = os.environ.get("SEC_USER_AGENT", "secrethon-underwriting contact@example.com")
    return {"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}


def _sec_get(url: str, params: dict | None = None) -> dict:
    """GET до SEC з кешем на диску й паузою (SEC просить ≤10 запитів на секунду)."""
    params = params or {}
    key = hashlib.sha256((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    path = CACHE_DIR / f"sec_{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    last_err = None
    for attempt in range(3):
        try:
            time.sleep(0.2)
            resp = requests.get(url, params=params, headers=_headers(), timeout=30)
            resp.raise_for_status()
            data = resp.json()
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        except requests.RequestException as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{url}: {last_err}")


def _pick(facts: dict, kind: str):
    best = (None, None, [], "")
    for taxonomy, tag in TAGS[kind]:
        node = facts.get("facts", {}).get(taxonomy, {}).get(tag)
        if not node:
            continue
        units = node.get("units", {})
        unit = "USD" if "USD" in units else (next(iter(units), None))
        if not unit:
            continue
        rows = units[unit]
        newest = max((r.get("end") or "" for r in rows), default="")
        if newest > best[3]:
            best = (tag, unit, rows, newest)
    return best[0], best[1], best[2]


def _latest_annual(rows: list):
    best = None
    for r in rows:
        if r.get("form") not in ANNUAL_FORMS or not r.get("end"):
            continue
        start = r.get("start")
        if start:  # потік за період: беремо лише ~річні періоди
            days = (_d(r["end"]) - _d(start)).days
            if not 330 <= days <= 400:
                continue
        if best is None or (r["end"], r.get("filed", "")) > (best["end"], best.get("filed", "")):
            best = r
    return best


def _latest_point(rows: list):
    """Остання звітна дата для залишку (будь-яка форма: 10-K, 10-Q, 20-F)."""
    best = None
    for r in rows:
        if not r.get("end") or r.get("start"):
            continue
        if best is None or (r["end"], r.get("filed", "")) > (best["end"], best.get("filed", "")):
            best = r
    return best


def _d(s: str):
    from datetime import date
    y, m, d = (int(x) for x in s.split("-"))
    return date(y, m, d)


STOP = {"inc", "corp", "corporation", "co", "company", "plc", "ltd", "limited", "llc",
        "the", "and", "ag", "sa", "nv", "holdings", "holding", "lp", "gmbh", "se"}


def _norm_name(name: str) -> list:
    words = re.sub(r"[^a-z0-9]+", " ", (name or "").lower().replace("&", " ")).split()
    return [w for w in words if w not in STOP]


def match_sponsor(sponsor: str, tickers: dict):
    sp = _norm_name(sponsor)
    if not sp:
        return None
    for row in tickers.values():
        tt = _norm_name(row.get("title", ""))
        if tt and (tt == sp or (sp[:len(tt)] == tt and len(tt) >= 1 and
                                 tt[0] == sp[0])):
            return int(row["cik_str"]), row["title"], row["ticker"]
    return None


def _fmt(v, unit):
    return f"{unit} {v:,.0f}" if unit != "USD" else f"${v:,.0f}"


class EdgarGetter(DataGetter):
    name = "edgar"

    def fetch(self, query: Query) -> list[dict]:
        drug = (query.mechanism or "").strip()
        if not drug:
            return []
        cik, company, ticker, verified = self._find_company(drug)
        if cik is None:
            print(f"[edgar] для «{drug}» не знайдено компанії, що подає звіти до SEC")
            return []
        facts = _sec_get(FACTS_URL.format(cik=cik))
        rec = self._build_record(drug, cik, company, ticker, verified, facts)
        if rec is None:
            print(f"[edgar] у XBRL {company} немає потрібних цифр")
            return []
        print(f"[edgar] {company} ({ticker}): запис із фінансами створено"
              f"{'' if verified else ' (спонсор НЕ підтверджено)'}")
        return [rec]

    def refine(self, query: Query, evidence: list):
        from collections import Counter
        drug = (query.mechanism or "").strip()
        counts = Counter(
            r["meta"].get("lead_sponsor") for r in evidence
            if r.get("source_type") == "nct_aact" and r["meta"].get("lead_sponsor"))
        if not counts:
            return None
        sponsor = counts.most_common(1)[0][0]
        found = match_sponsor(sponsor, _sec_get(TICKERS_URL))
        if not found:
            print(f"[edgar] спонсор з реєстру «{sponsor}» не подає звіти до SEC "
                  f"(або назву не знайдено): запис про фінанси не створюється")
            return [], {"sec_filings"}
        cik, company, ticker = found
        facts = _sec_get(FACTS_URL.format(cik=cik))
        rec = self._build_record(drug, cik, company, ticker, True, facts)
        if rec is None:
            return [], {"sec_filings"}
        rec["meta"]["sponsor_source"] = f"registry lead sponsor: {sponsor}"
        print(f"[edgar] спонсор з реєстру «{sponsor}» -> {company} ({ticker})")
        return [rec], {"sec_filings"}

    def _find_company(self, drug: str):
        key = drug.lower()
        if key in SPONSORS and SPONSORS[key] is None:
            return None, None, None, False
        ticker = SPONSORS.get(key)
        tickers = _sec_get(TICKERS_URL)
        if ticker:
            for row in tickers.values():
                if row.get("ticker", "").upper() == ticker:
                    return int(row["cik_str"]), row["title"], ticker, True
            print(f"[edgar] тикер {ticker} не знайдено у списку SEC (компанію могли "
                  f"поглинути)")
            return None, None, None, False
        if os.environ.get("EDGAR_ALLOW_UNVERIFIED") != "1":
            print(f"[edgar] спонсора «{drug}» немає в SPONSORS; пошук за текстом "
                  f"вимкнено (EDGAR_ALLOW_UNVERIFIED=1 вмикає)")
            return None, None, None, False
        try:
            data = _sec_get(SEARCH_URL, {"q": f'"{drug}"', "forms": "10-K,20-F"})
            for hit in data.get("hits", {}).get("hits", []):
                ciks = hit.get("_source", {}).get("ciks", [])
                names = hit.get("_source", {}).get("display_names", [])
                if ciks:
                    cik = int(ciks[0])
                    ticker = next((r["ticker"] for r in tickers.values()
                                   if int(r["cik_str"]) == cik), "")
                    name = re.sub(r"\(CIK[^)]*\)|\([A-Z.,\s]+\)", "",
                                  names[0] if names else f"CIK {cik}")
                    return cik, re.sub(r"\s+", " ", name).strip(), ticker, False
        except Exception as e:
            print(f"[edgar] повнотекстовий пошук не вдався: {e}")
        return None, None, None, False

    def _build_record(self, drug, cik, company, ticker, verified, facts):
        rd_tag, rd_unit, rd_rows = _pick(facts, "rd")
        cash_tag, cash_unit, cash_rows = _pick(facts, "cash")
        op_tag, op_unit, op_rows = _pick(facts, "opcf")
        rd = _latest_annual(rd_rows)
        cash = _latest_point(cash_rows)
        op = _latest_annual(op_rows)
        if not (rd or cash or op):
            return None

        sents = [f"SEC EDGAR financial data for {company}"
                 f"{f' ({ticker})' if ticker else ''}, company-wide figures from XBRL "
                 f"filings (not specific to {drug})."]
        meta = {"company": company, "ticker": ticker, "cik": cik,
                "sponsor_verified": verified, "drug": drug}
        if rd:
            sents.append(f"Research and development expense for the fiscal year "
                         f"ended {rd['end']} was {_fmt(rd['val'], rd_unit)}.")
            meta.update(rd_value=rd["val"], rd_unit=rd_unit, rd_fy_end=rd["end"])
        if cash:
            sents.append(f"Cash and cash equivalents as of {cash['end']} were "
                         f"{_fmt(cash['val'], cash_unit)}.")
            meta.update(cash_value=cash["val"], cash_unit=cash_unit,
                        cash_date=cash["end"])
        if op:
            word = "used in" if op["val"] < 0 else "provided by"
            sents.append(f"Net cash {word} operating activities for the fiscal year "
                         f"ended {op['end']} was {_fmt(abs(op['val']), op_unit)}.")
            meta.update(opcf_value=op["val"], opcf_unit=op_unit, opcf_fy_end=op["end"])
        return {
            "id": f"E_SEC_{cik}",
            "source_type": "sec_filings",
            "source_id": f"CIK:{cik}",
            "url": BROWSE_URL.format(cik=cik),
            "title": f"SEC EDGAR financials: {company}",
            "text": " ".join(sents),
            "meta": meta,
        }