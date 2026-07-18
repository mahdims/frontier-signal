from frontier_signal.collectors.bluesky import BlueskyCollector
from frontier_signal.collectors.x import XCollector
from frontier_signal.schemas import SourceConfig
from frontier_signal.settings import settings


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_x_collector_builds_public_post(monkeypatch):
    monkeypatch.setattr(settings, "x_bearer_token", "test-token")
    monkeypatch.setattr(
        "frontier_signal.collectors.x.httpx.get",
        lambda *args, **kwargs: FakeResponse(
            {
                "data": [
                    {
                        "id": "123",
                        "text": "A technical result",
                        "author_id": "42",
                        "created_at": "2026-07-17T12:00:00Z",
                        "lang": "en",
                        "public_metrics": {"like_count": 10},
                    }
                ],
                "includes": {"users": [{"id": "42", "username": "researcher"}]},
            }
        ),
    )
    source = SourceConfig(id="x", name="X", type="x", config={"query": "AI"})

    item = XCollector().collect(source)[0]

    assert item.url == "https://x.com/researcher/status/123"
    assert item.metadata["public_metrics"]["like_count"] == 10


def test_bluesky_collector_builds_public_post(monkeypatch):
    monkeypatch.setattr(
        "frontier_signal.collectors.bluesky.httpx.get",
        lambda *args, **kwargs: FakeResponse(
            {
                "posts": [
                    {
                        "uri": "at://did:plc:abc/app.bsky.feed.post/xyz",
                        "cid": "cid",
                        "author": {"handle": "researcher.bsky.social"},
                        "record": {
                            "text": "A new benchmark",
                            "createdAt": "2026-07-17T12:00:00Z",
                            "langs": ["en"],
                        },
                        "likeCount": 4,
                    }
                ]
            }
        ),
    )
    source = SourceConfig(
        id="bluesky", name="Bluesky", type="bluesky", config={"query": "AI"}
    )

    item = BlueskyCollector().collect(source)[0]

    assert item.url == "https://bsky.app/profile/researcher.bsky.social/post/xyz"
    assert item.metadata["likes"] == 4
