from frontier_signal.db import canonicalize_url


def test_canonicalize_url_removes_tracking():
    assert canonicalize_url("https://example.com/a?utm_source=x&x=1#top") == "https://example.com/a?x=1"
