from __future__ import annotations

import httpx

from .base import Collector
from frontier_signal.schemas import RawItem, SourceConfig
from frontier_signal.settings import settings


class XCollector(Collector):
    endpoint = "https://api.x.com/2/tweets/search/recent"

    def collect(self, source: SourceConfig) -> list[RawItem]:
        if not settings.x_bearer_token:
            raise RuntimeError("X_BEARER_TOKEN is required for X collection")

        max_results = max(10, min(100, int(source.config.get("max_results", 25))))
        response = httpx.get(
            self.endpoint,
            headers={"Authorization": f"Bearer {settings.x_bearer_token}"},
            params={
                "query": source.config["query"],
                "max_results": max_results,
                "sort_order": "recency",
                "tweet.fields": "author_id,created_at,lang,public_metrics",
                "expansions": "author_id",
                "user.fields": "name,username,verified",
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        users = {user["id"]: user for user in payload.get("includes", {}).get("users", [])}

        items: list[RawItem] = []
        for post in payload.get("data", []):
            author = users.get(post.get("author_id"), {})
            username = author.get("username")
            url = f"https://x.com/{username or 'i'}/status/{post['id']}"
            text = " ".join((post.get("text") or "").split())
            items.append(
                RawItem(
                    source_id=source.id,
                    source_type=source.type,
                    external_id=post["id"],
                    url=url,
                    title=text[:180],
                    content=text,
                    author_name=username or author.get("name"),
                    language=post.get("lang") or source.language,
                    region=source.region,
                    published_at=post.get("created_at"),
                    metadata={
                        "platform": "x",
                        "public_metrics": post.get("public_metrics", {}),
                        "verified_author": author.get("verified", False),
                    },
                )
            )
        return items
