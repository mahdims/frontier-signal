from __future__ import annotations

import hashlib
from urllib.parse import urlencode
import feedparser

from .base import Collector
from frontier_signal.schemas import RawItem, SourceConfig


class ArxivCollector(Collector):
    endpoint = "https://export.arxiv.org/api/query"

    def collect(self, source: SourceConfig) -> list[RawItem]:
        query = source.config["query"]
        max_results = int(source.config.get("max_results", 50))
        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        feed = feedparser.parse(f"{self.endpoint}?{urlencode(params)}")
        items: list[RawItem] = []
        for entry in feed.entries:
            url = entry.link
            external_id = getattr(entry, "id", url).rsplit("/", 1)[-1]
            authors = ", ".join(a.name for a in getattr(entry, "authors", []))
            categories = [t.term for t in getattr(entry, "tags", [])]
            items.append(RawItem(
                source_id=source.id,
                source_type=source.type,
                external_id=external_id,
                url=url,
                title=" ".join(entry.title.split()),
                content=" ".join(getattr(entry, "summary", "").split()),
                author_name=authors or None,
                language=source.language,
                region=source.region,
                published_at=getattr(entry, "published", None),
                metadata={"categories": categories, "pdf_url": url.replace("/abs/", "/pdf/")},
            ))
        return items
