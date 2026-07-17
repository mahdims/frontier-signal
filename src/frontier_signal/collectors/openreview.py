from __future__ import annotations

from datetime import datetime, timezone
import openreview

from .base import Collector
from frontier_signal.schemas import RawItem, SourceConfig


def content_value(value):
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


class OpenReviewCollector(Collector):
    def collect(self, source: SourceConfig) -> list[RawItem]:
        venue_id = source.config["venue_id"]
        limit = int(source.config.get("limit", 500))
        client = openreview.api.OpenReviewClient(baseurl="https://api2.openreview.net")
        notes = client.get_all_notes(content={"venueid": venue_id})[:limit]
        items: list[RawItem] = []
        for note in notes:
            content = note.content or {}
            title = content_value(content.get("title", ""))
            abstract = content_value(content.get("abstract", ""))
            authors = content_value(content.get("authors", [])) or []
            cdate = getattr(note, "cdate", None)
            published = datetime.fromtimestamp(cdate / 1000, tz=timezone.utc) if cdate else None
            forum = getattr(note, "forum", note.id)
            url = f"https://openreview.net/forum?id={forum}"
            items.append(RawItem(
                source_id=source.id,
                source_type=source.type,
                external_id=note.id,
                url=url,
                title=title,
                content=abstract,
                author_name=", ".join(authors) if isinstance(authors, list) else str(authors),
                language=source.language,
                region=source.region,
                published_at=published,
                metadata={"venue_id": venue_id, "forum": forum},
            ))
        return items
