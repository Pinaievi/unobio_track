import json
from collections import Counter
from pathlib import Path

data = json.loads(Path("results/evidence_raw.json").read_text(encoding="utf-8"))
ev = data["evidence"]

print("Записи за source_type:")
for k, n in Counter(r["source_type"] for r in ev).most_common():
    print(f"  {n:>3}  {k}")

# found_by_all: усі запити, що знайшли статтю (found_by лишає тільки найважливіший)
print("\nСтатті за запитом:")
tags = Counter(t for r in ev for t in r["meta"].get("found_by_all", []))
for k, n in tags.most_common():
    print(f"  {n:>3}  {k}")

for tag in ("tissue_search", "pk_search", "epidemiology_search"):
    print(f"\n{tag}:")
    for r in ev:
        if tag in r["meta"].get("found_by_all", []):
            print("  -", r["title"][:110])