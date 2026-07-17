from __future__ import annotations

from .collectors import COLLECTORS
from .config import load_sources
from .db import save_items


def collect_all(source_id: str | None = None) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for source in load_sources():
        if source_id and source.id != source_id:
            continue
        if not source.enabled:
            continue
        if source.type in {"manual_web", "manual_private"}:
            continue
        collector_cls = COLLECTORS.get(source.type)
        if not collector_cls:
            result[source.id] = {"status": "skipped", "reason": "no collector"}
            continue
        try:
            items = collector_cls().collect(source)
            inserted, skipped = save_items(items)
            result[source.id] = {
                "status": "ok",
                "collected": len(items),
                "inserted": inserted,
                "skipped": skipped,
            }
        except Exception as exc:
            result[source.id] = {"status": "error", "error": str(exc)}
    return result
