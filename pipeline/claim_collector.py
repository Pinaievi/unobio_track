"""
claim_collector.py — витягує факти (claims) із частин evidence через LLM.

  results/evidence/evidence_part_*.json  ->  results/claims.json

Що нового порівняно зі старою версією:
  - частини обробляються ПАРАЛЕЛЬНО (за замовчуванням 4 потоки);
  - кожен виклик пише токени, час і вартість у results/run_log.jsonl
    (крок "claims:<ім'я частини>"), тож у README є чесна вартість запуску;
  - повторні спроби з паузою (429, мережа, невалідний JSON);
  - завантажений файл видаляється з сервера після виклику;
  - якщо частина не оброблена після всіх спроб, claims усе одно зберігаються,
    але скрипт завершується з помилкою — щоб конвеєр не мовчки втратив докази;
  - промпт береться з extraction_prompt.txt (одне джерело правди).

Запуск:
  python claim_collector.py
  python claim_collector.py --workers 2      # якщо API відповідає 429 (ліміти)
"""

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

import dotenv
from google import genai
from pydantic import BaseModel, Field
import prompts

from core.config import PRICE_OUT_PER_M, PRICE_IN_PER_M

# ---------------------------------------------------------------- налаштування

MODEL = "gemini-3.1-flash-lite"
MAX_RETRIES = 3
DEFAULT_WORKERS = 4

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
FOLDER = RESULTS / "evidence"
OUTPUT_FILE = RESULTS / "claims.json"
LOG_PATH = RESULTS / "run_log.jsonl"
PROMPT_PATH = ROOT / "extraction_prompt.txt"


# ---------------------------------------------------------------- схема відповіді

class Claim(BaseModel):
    claim: str
    evidence_id: str
    quote: str = Field(description="One continuous fragment copied exactly from the record. "
                                   "No '...' inside.")
    stage: Literal["unmet_need", "mechanism", "translation", "clinical",
                   "competition", "regulatory", "safety_or_failure", "other"]
    direction: Literal["supports", "contradicts", "neutral"] = Field(
        description="supports: positive result for the drug. contradicts: negative or "
                    "cautionary result (failure, early stop, safety signal, no efficacy). "
                    "neutral: design, enrollment, phase, status, background."
    )
    confidence: Literal["high", "medium", "low"]


class ClaimsResponse(BaseModel):
    claims: list[Claim]


# ---------------------------------------------------------------- допоміжні

_log_lock = threading.Lock()
_totals = {"in": 0, "out": 0, "cost": 0.0, "calls": 0}


def read_usage(interaction, prompt_chars: int, out_text: str):
    """Токени з відповіді API; якщо поле не знайшлось — груба оцінка (довжина/4)."""
    usage = getattr(interaction, "usage", None) or getattr(
        interaction, "usage_metadata", None)
    tin = tout = None
    if usage is not None:
        for name in ("total_input_tokens", "input_tokens", "prompt_token_count"):
            v = getattr(usage, name, None)
            if isinstance(v, int):
                tin = v
                break
        for name in ("total_output_tokens", "output_tokens",
                     "candidates_token_count"):
            v = getattr(usage, name, None)
            if isinstance(v, int):
                tout = v
                break
    estimated = tin is None or tout is None
    if tin is None:
        tin = max(1, prompt_chars // 4)
    if tout is None:
        tout = max(1, len(out_text) // 4)
    return tin, tout, estimated


def log_call(step: str, attempt: int, tin: int, tout: int, estimated: bool,
             seconds: float):
    cost = tin / 1e6 * PRICE_IN_PER_M + tout / 1e6 * PRICE_OUT_PER_M
    entry = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "step": step, "model": MODEL, "attempt": attempt,
        "input_tokens": tin, "output_tokens": tout,
        "tokens_estimated": estimated, "cost_usd": round(cost, 6),
        "seconds": round(seconds, 2),
    }
    with _log_lock:  # кілька потоків пишуть в один файл
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        _totals["in"] += tin
        _totals["out"] += tout
        _totals["cost"] += cost
        _totals["calls"] += 1
    return cost


def process_part(client, prompt: str, path: Path):
    """Одна частина evidence -> список claims. Кидає виняток, якщо всі спроби невдалі."""
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        uploaded = None
        t0 = time.time()
        try:
            uploaded = client.files.upload(file=path)
            interaction = client.interactions.create(
                model=MODEL,
                input=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "document",
                        "uri": uploaded.uri,
                        "mime_type": uploaded.mime_type,
                    },
                ],
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": ClaimsResponse.model_json_schema(),
                },
            )
            out = interaction.output_text
            parsed = ClaimsResponse.model_validate_json(out)
            tin, tout, est = read_usage(
                interaction, len(prompt) + path.stat().st_size, out)
            cost = log_call(f"claims:{path.stem}", attempt, tin, tout, est,
                            time.time() - t0)
            return [c.model_dump() for c in parsed.claims], tin, tout, cost
        except Exception as e:  # ліміти, мережа, невалідний JSON
            last_err = e
            print(f"  [{path.name}] спроба {attempt}/{MAX_RETRIES} не вдалась: {e}")
            time.sleep(3 * attempt)
        finally:
            if uploaded is not None:
                try:
                    client.files.delete(name=uploaded.name)
                except Exception:
                    pass  # не критично: файл і так зникне з сервера за терміном
    raise RuntimeError(f"{path.name}: {last_err}")


# ---------------------------------------------------------------- головна логіка

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                    help="скільки частин обробляти одночасно")
    args = ap.parse_args()

    prompt = prompts.EXTRACTION_PROMPT

    dotenv.load_dotenv()
    key = os.environ.get("API_KEY")
    if not key:
        sys.exit("Немає API_KEY у .env")

    parts = sorted(FOLDER.glob("evidence_part_*.json"))
    if not parts:
        sys.exit(f"Немає частин evidence у {FOLDER}. Спершу запусти split_evidence.py.")

    RESULTS.mkdir(exist_ok=True)
    client = genai.Client(api_key=key)

    print(f"Частин evidence: {len(parts)}, потоків: {args.workers}, модель: {MODEL}")
    t_start = time.time()
    by_part: dict[Path, list] = {}
    failed: list[str] = []

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(process_part, client, prompt, p): p for p in parts}
        for fut in as_completed(futures):
            p = futures[fut]
            try:
                claims, tin, tout, cost = fut.result()
                by_part[p] = claims
                print(f"  [{p.name}] claims: {len(claims)}, токени {tin}+{tout}, "
                      f"~${cost:.4f}", flush=True)
            except Exception as e:
                failed.append(f"{p.name}: {e}")
                print(f"  [{p.name}] НЕ ОБРОБЛЕНО: {e}", flush=True)

    # порядок claims такий самий, як порядок частин, незалежно від того, хто швидше
    all_claims = []
    for p in parts:
        all_claims.extend(by_part.get(p, []))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"claims": all_claims}, f, ensure_ascii=False, indent=2)

    dt = time.time() - t_start
    print(f"\nГотово: {len(all_claims)} claims із {len(by_part)}/{len(parts)} частин "
          f"за {dt:.0f} с -> {OUTPUT_FILE.name}")
    print(f"Викликів: {_totals['calls']}, токени: {_totals['in']} вхід / "
          f"{_totals['out']} вихід, ~${_totals['cost']:.4f}")

    if failed:
        print("\nУВАГА: частини без claims (докази втрачено):")
        for line in failed:
            print("  " + line)
        sys.exit(1)


if __name__ == "__main__":
    main()