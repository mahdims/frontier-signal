from __future__ import annotations

import hashlib
import feedparser
import httpx
from bs4 import BeautifulSoup

from .base import Collector
from frontier_signal.schemas import RawItem, SourceConfig


class RSSCollector(Collector):
    def collect(self, source: SourceConfig) -> list[RawItem]:
        url = source.config["feed_url"]
        response = None
        for _ in range(2):
            response = httpx.get(
                url,
                timeout=30,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; FrontierSignal/0.1)",
                    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
                },
            )
            if response.status_code not in {403, 429} and response.status_code < 500:
                break
        assert response is not None
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        max_items = max(1, int(source.config.get("max_items", 20)))
        keywords = [str(x).lower() for x in source.config.get("keywords", [])]
        items: list[RawItem] = []
        for entry in feed.entries:
            item_url = getattr(entry, "link", source.homepage or url)
            external_id = str(getattr(entry, "id", "")) or hashlib.sha256(item_url.encode()).hexdigest()
            raw_content = getattr(entry, "summary", "") or getattr(entry, "description", "")
            content = BeautifulSoup(raw_content, "html.parser").get_text(" ", strip=True)
            content = content[: int(source.config.get("max_content_chars", 20000))]
            haystack = f"{getattr(entry, 'title', '')} {content}".lower()
            if keywords and not any(keyword in haystack for keyword in keywords):
                continue
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
            if len(items) >= max_items:
                break
        return items
