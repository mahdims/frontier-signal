from __future__ import annotations

import httpx

from .base import Collector
from frontier_signal.schemas import RawItem, SourceConfig


class HackerNewsCollector(Collector):
    base = "https://hacker-news.firebaseio.com/v0"

    def collect(self, source: SourceConfig) -> list[RawItem]:
        mode = source.config.get("mode", "new")
        max_items = int(source.config.get("max_items", 100))
        keywords = [x.lower() for x in source.config.get("keywords", [])]

        ids = httpx.get(f"{self.base}/{mode}stories.json", timeout=30).json()[:max_items]
        items: list[RawItem] = []
        with httpx.Client(timeout=20) as client:
            for item_id in ids:
                data = client.get(f"{self.base}/item/{item_id}.json").json()
                if not data or data.get("type") != "story":
                    continue
                haystack = f"{data.get('title', '')} {data.get('text', '')}".lower()
                if keywords and not any(k in haystack for k in keywords):
                    continue
                url = data.get("url") or f"https://news.ycombinator.com/item?id={item_id}"
                items.append(RawItem(
                    source_id=source.id,
                    source_type=source.type,
                    external_id=str(item_id),
                    url=url,
                    title=data.get("title", ""),
                    content=data.get("text", ""),
                    author_name=data.get("by"),
                    language=source.language,
                    region=source.region,
                    published_at=data.get("time"),
                    metadata={
                        "hn_discussion": f"https://news.ycombinator.com/item?id={item_id}",
                        "score": data.get("score", 0),
                        "descendants": data.get("descendants", 0),
                    },
                ))
        return items
