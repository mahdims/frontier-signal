from frontier_signal.runner import COLLECTORS, collect_all
from frontier_signal.schemas import SourceConfig


class FailingCollector:
    def collect(self, source):
        raise RuntimeError("simulated API failure")


class WorkingCollector:
    def collect(self, source):
        return []


def test_collector_failure_does_not_abort_other_sources(monkeypatch):
    sources = [
        SourceConfig(id="x", name="X", type="failing"),
        SourceConfig(id="rss", name="RSS", type="working"),
    ]
    monkeypatch.setattr("frontier_signal.runner.load_sources", lambda: sources)
    monkeypatch.setitem(COLLECTORS, "failing", FailingCollector)
    monkeypatch.setitem(COLLECTORS, "working", WorkingCollector)

    result = collect_all()

    assert result["x"] == {"status": "error", "error": "simulated API failure"}
    assert result["rss"]["status"] == "ok"
