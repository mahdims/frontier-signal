from __future__ import annotations

import hashlib
import re
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
import httpx

from .base import Collector
from frontier_signal.schemas import RawItem, SourceConfig


class WebCollector(Collector):
    """Conservative scraper for public article-list pages.

    Each source supplies an article URL regex. Links remain restricted to the configured
    host unless allow_external_links is explicitly enabled.
    """

    user_agent = "Mozilla/5.0 (compatible; FrontierSignal/0.1; public-news-monitor)"

    def collect(self, source: SourceConfig) -> list[RawItem]:
        list_url = source.config.get("list_url") or source.homepage
        if not list_url:
            raise ValueError(f"Source {source.id} requires list_url or homepage")

        max_items = max(1, min(20, int(source.config.get("max_items", 5))))
        keywords = [str(x).lower() for x in source.config.get("keywords", [])]
        pattern = re.compile(source.config.get("article_url_pattern", r"."))
        selector = source.config.get("link_selector", "a[href]")
        allow_external = bool(source.config.get("allow_external_links", False))
        fetch_details = bool(source.config.get("fetch_details", True))

        headers = {"User-Agent": self.user_agent, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7"}
        with httpx.Client(headers=headers, follow_redirects=True, timeout=20) as client:
            self._check_robots(client, list_url)
            response = client.get(list_url)
            response.raise_for_status()
            final_url = str(response.url)
            host = urlparse(final_url).netloc
            soup = BeautifulSoup(response.text, "html.parser")

            candidates: list[tuple[str, str]] = []
            seen: set[str] = set()
            for anchor in soup.select(selector):
                title = " ".join(anchor.get_text(" ", strip=True).split())
                item_url = urljoin(final_url, anchor.get("href", ""))
                parsed = urlparse(item_url)
                if len(title) < 8 or parsed.scheme not in {"http", "https"}:
                    continue
                if not allow_external and parsed.netloc != host:
                    continue
                if not pattern.search(parsed.path) or item_url in seen:
                    continue
                if keywords and not any(keyword in title.lower() for keyword in keywords):
                    continue
                seen.add(item_url)
                candidates.append((title, item_url))
                if len(candidates) >= max_items:
                    break

            items: list[RawItem] = []
            for title, item_url in candidates:
                content = ""
                published_at = None
                if fetch_details:
                    try:
                        content, published_at = self._fetch_detail(client, item_url)
                    except httpx.HTTPError:
                        pass
                items.append(
                    RawItem(
                        source_id=source.id,
                        source_type=source.type,
                        external_id=hashlib.sha256(item_url.encode()).hexdigest(),
                        url=item_url,
                        title=title,
                        content=content,
                        language=source.language,
                        region=source.region,
                        published_at=published_at,
                        metadata={"list_url": list_url, "collection_method": "public_html"},
                    )
                )
            return items

    def _check_robots(self, client: httpx.Client, url: str) -> None:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            response = client.get(robots_url)
            if response.status_code != 200:
                return
            robots = RobotFileParser()
            robots.set_url(robots_url)
            robots.parse(response.text.splitlines())
            if not robots.can_fetch(self.user_agent, url):
                raise RuntimeError(f"robots.txt disallows collection from {url}")
        except httpx.HTTPError:
            return

    def _fetch_detail(self, client: httpx.Client, url: str) -> tuple[str, str | None]:
        response = client.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        description = ""
        for attrs in (
            {"property": "og:description"},
            {"name": "description"},
        ):
            tag = soup.find("meta", attrs=attrs)
            if tag and tag.get("content"):
                description = str(tag["content"]).strip()
                break

        paragraphs = [
            " ".join(p.get_text(" ", strip=True).split())
            for p in soup.select("article p, .article-content p, .content p")
        ]
        body = " ".join(p for p in paragraphs if len(p) >= 20)[:8000]
        content = body or description

        published_at = None
        time_tag = soup.find("meta", attrs={"property": "article:published_time"})
        if time_tag and time_tag.get("content"):
            published_at = str(time_tag["content"])
        else:
            time_node = soup.find("time", attrs={"datetime": True})
            if time_node:
                published_at = str(time_node["datetime"])
        return content, published_at
