from __future__ import annotations

import httpx

from .base import Collector
from frontier_signal.schemas import RawItem, SourceConfig
from frontier_signal.settings import settings


class YouTubeCollector(Collector):
    endpoint = "https://www.googleapis.com/youtube/v3/search"

    def collect(self, source: SourceConfig) -> list[RawItem]:
        if not settings.youtube_api_key:
            raise RuntimeError("YOUTUBE_API_KEY is required")
        results: list[RawItem] = []
        for query in source.config.get("queries", []):
            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "order": "date",
                "maxResults": source.config.get("max_results_per_query", 10),
                "key": settings.youtube_api_key,
            }
            payload = httpx.get(self.endpoint, params=params, timeout=30).json()
            for item in payload.get("items", []):
                video_id = item["id"]["videoId"]
                snippet = item["snippet"]
                results.append(RawItem(
                    source_id=source.id,
                    source_type=source.type,
                    external_id=video_id,
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    title=snippet["title"],
                    content=snippet.get("description", ""),
                    author_name=snippet.get("channelTitle"),
                    language=source.language,
                    region=source.region,
                    published_at=snippet.get("publishedAt"),
                    metadata={"query": query, "channel_id": snippet.get("channelId")},
                ))
        return results
