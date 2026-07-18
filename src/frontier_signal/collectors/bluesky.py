from __future__ import annotations

import httpx

from .base import Collector
from frontier_signal.schemas import RawItem, SourceConfig


class BlueskyCollector(Collector):
    endpoint = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"

    def collect(self, source: SourceConfig) -> list[RawItem]:
        limit = max(1, min(100, int(source.config.get("limit", 25))))
        response = httpx.get(
            self.endpoint,
            params={"q": source.config["query"], "sort": "latest", "limit": limit},
            timeout=30,
        )
        response.raise_for_status()

        items: list[RawItem] = []
        for post in response.json().get("posts", []):
            record = post.get("record", {})
            author = post.get("author", {})
            text = " ".join((record.get("text") or "").split())
            rkey = post.get("uri", "").rsplit("/", 1)[-1]
            handle = author.get("handle", "unknown")
            items.append(
                RawItem(
                    source_id=source.id,
                    source_type=source.type,
                    external_id=post.get("uri") or post.get("cid"),
                    url=f"https://bsky.app/profile/{handle}/post/{rkey}",
                    title=text[:180],
                    content=text,
                    author_name=handle,
                    language=(record.get("langs") or [source.language])[0],
                    region=source.region,
                    published_at=record.get("createdAt") or post.get("indexedAt"),
                    metadata={
                        "platform": "bluesky",
                        "likes": post.get("likeCount", 0),
                        "reposts": post.get("repostCount", 0),
                        "replies": post.get("replyCount", 0),
                    },
                )
            )
        return items
