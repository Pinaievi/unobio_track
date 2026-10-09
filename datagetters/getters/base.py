"""Базові типи та спільний HTTP-клієнт із кешем на диску."""

import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import requests

CACHE_DIR = Path(".cache")
CACHE_DIR.mkdir(exist_ok=True)
HEADERS = {"User-Agent": "secrethon-underwriting/0.1"}


@dataclass(frozen=True)
class Query:
    indication: str = ""
    mechanism: str = ""


class DataGetter(ABC):
    """Одне джерело даних. Успадковуйся, задай name і реалізуй fetch()."""

    name: str = "unnamed"

    @abstractmethod
    def fetch(self, query: Query) -> list[dict]:
        """Повернути список записів evidence:
        {id, source_type, source_id, url, title, text, meta}"""


def get_json(url: str, params: dict | None = None, timeout: int = 30) -> dict:
    """GET із кешем і трьома спробами."""
    params = params or {}
    key = hashlib.sha256((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    last_err = None
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        except requests.RequestException as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{url}: {last_err}")