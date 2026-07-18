import pytest

from frontier_signal.collectors.rss import RSSCollector
from frontier_signal.collectors.web import WebCollector
from frontier_signal.config import load_sources, load_yaml
from frontier_signal.schemas import SourceConfig
from frontier_signal.settings import settings


class FakeResponse:
    def __init__(self, content=b"", text="", url="https://example.com/news"):
        self.content = content
        self.text = text
        self.url = url
        self.status_code = 200

    def raise_for_status(self):
        return None


def test_rss_collector_filters_keywords_and_caps_items(monkeypatch):
    feed = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Feed</title>
    <item><guid>1</guid><link>https://example.com/1</link><title>AI model release</title></item>
    <item><guid>2</guid><link>https://example.com/2</link><title>Sports result</title></item>
    <item><guid>3</guid><link>https://example.com/3</link><title>AI benchmark</title></item>
    </channel></rss>"""
    monkeypatch.setattr(
        "frontier_signal.collectors.rss.httpx.get",
        lambda *args, **kwargs: FakeResponse(content=feed),
    )
    source = SourceConfig(
        id="feed",
        name="Feed",
        type="rss",
        config={"feed_url": "https://example.com/feed", "keywords": ["AI"], "max_items": 1},
    )

    items = RSSCollector().collect(source)

    assert [item.title for item in items] == ["AI model release"]


class FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def get(self, url):
        if url == "https://example.com/robots.txt":
            return FakeResponse(text="User-agent: *\nAllow: /", url=url)
        if url == "https://example.com/news":
            return FakeResponse(
                text='<a href="/article/1">New AI benchmark result</a>',
                url=url,
            )
        return FakeResponse(
            text='<meta name="description" content="Detailed benchmark summary">',
            url=url,
        )


def test_web_collector_uses_source_url_rule(monkeypatch):
    monkeypatch.setattr("frontier_signal.collectors.web.httpx.Client", FakeClient)
    source = SourceConfig(
        id="web",
        name="Web",
        type="web",
        homepage="https://example.com/news",
        config={"article_url_pattern": r"^/article/[0-9]+$", "keywords": ["AI"]},
    )

    item = WebCollector().collect(source)[0]

    assert item.url == "https://example.com/article/1"
    assert item.content == "Detailed benchmark summary"


class DisallowClient(FakeClient):
    def get(self, url):
        if url.endswith("/robots.txt"):
            return FakeResponse(text="User-agent: *\nDisallow: /news", url=url)
        return super().get(url)


def test_web_collector_respects_robots_txt(monkeypatch):
    monkeypatch.setattr("frontier_signal.collectors.web.httpx.Client", DisallowClient)
    source = SourceConfig(
        id="web",
        name="Web",
        type="web",
        homepage="https://example.com/news",
    )

    with pytest.raises(RuntimeError, match="robots.txt disallows"):
        WebCollector().collect(source)


def test_china_registry_contains_all_requested_sources():
    assert len(load_yaml(settings.config_dir / "china_sources.yaml")["sources"]) == 50
    registry_ids = {
        source.id
        for source in load_sources()
        if source.id in {
            "jiqizhixin",
            "qbitai",
            "chinai_newsletter",
            "scmp_china_tech",
            "deepseek_official_news",
        }
    }

    assert registry_ids == {
        "jiqizhixin",
        "qbitai",
        "chinai_newsletter",
        "scmp_china_tech",
        "deepseek_official_news",
    }
