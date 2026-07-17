from __future__ import annotations

import json
from pathlib import Path
from frontier_signal.schemas import RawItem


def load_jsonl(path: Path) -> list[RawItem]:
    items: list[RawItem] = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            data = json.loads(line)
            data.setdefault("source_type", "manual")
            data.setdefault("external_id", f"{path.name}:{line_number}")
            items.append(RawItem.model_validate(data))
    return items
