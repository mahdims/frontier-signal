from __future__ import annotations

import hashlib
import feedparser

from .base import Collector
from frontier_signal.schemas import RawItem, SourceConfig


class RSSCollector(Collector):
    def collect(self, source: SourceConfig) -> list[RawItem]:
        url = source.config["feed_url"]
        feed = feedparser.parse(url)
        items: list[RawItem] = []
        for entry in feed.entries:
            item_url = getattr(entry, "link", source.homepage or url)
            external_id = str(getattr(entry, "id", "")) or hashlib.sha256(item_url.encode()).hexdigest()
            content = getattr(entry, "summary", "") or getattr(entry, "description", "")
            author = getattr(entry, "author", None)
            items.append(RawItem(
                source_id=source.id,
                source_type=source.type,
                external_id=external_id,
                url=item_url,
                title=" ".join(getattr(entry, "title", "").split()),
                content=" ".join(content.split()),
                author_name=author,
                language=source.language,
                region=source.region,
                published_at=getattr(entry, "published", None),
                metadata={"feed_url": url},
            ))
        return items
