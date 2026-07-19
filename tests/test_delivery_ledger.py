from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import frontier_signal.db as db
from frontier_signal.report import render_daily
from frontier_signal.schemas import ItemAnalysis, RawItem
from frontier_signal.settings import settings


def configure_test_database(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    session_factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "SessionLocal", session_factory)
    monkeypatch.setattr(settings, "output_dir", tmp_path / "outputs")
    db.Base.metadata.create_all(engine)


def add_analysis():
    db.save_items(
        [
            RawItem(
                source_id="source",
                source_type="rss",
                external_id="item-1",
                url="https://example.com/item-1",
                title="Unique signal",
            )
        ]
    )
    with db.SessionLocal() as session:
        item_id = session.scalar(select(db.ItemRow.id))
    db.save_analysis(
        item_id,
        ItemAnalysis(summary="Important result", priority_score=80),
    )


def test_pending_report_is_reused_and_delivered_items_are_excluded(monkeypatch, tmp_path):
    configure_test_database(monkeypatch, tmp_path)
    add_analysis()

    first = render_daily()
    retry = render_daily()

    assert retry.report_id == first.report_id
    assert retry.reused_pending is True
    assert "Unique signal" in retry.path.read_text()
    assert "Unique signal" in retry.email_path.read_text()
    assert "**Atomic claims**" not in retry.email_path.read_text()

    assert db.mark_report_delivered(first.report_id) is True
    next_report = render_daily()

    assert next_report.report_id != first.report_id
    assert "Items: 0." in next_report.path.read_text()
    with db.SessionLocal() as session:
        included = session.scalars(select(db.ReportItemRow)).all()
        assert len(included) == 1


def test_include_reported_is_an_explicit_override(monkeypatch, tmp_path):
    configure_test_database(monkeypatch, tmp_path)
    add_analysis()
    first = render_daily()
    db.mark_report_delivered(first.report_id)

    override = render_daily(include_reported=True)

    assert override.report_id != first.report_id
    assert "Unique signal" in override.path.read_text()
    assert override.reused_pending is False


def test_prune_pending_removes_only_unanalysed_stale_or_disabled_items(
    monkeypatch, tmp_path
):
    configure_test_database(monkeypatch, tmp_path)
    now = datetime.now(timezone.utc)
    db.save_items(
        [
            RawItem(
                source_id="active",
                source_type="rss",
                external_id="fresh",
                url="https://example.com/fresh",
                title="Fresh",
                published_at=now,
            ),
            RawItem(
                source_id="active",
                source_type="rss",
                external_id="stale",
                url="https://example.com/stale",
                title="Stale",
                published_at=now - timedelta(days=8),
            ),
            RawItem(
                source_id="disabled",
                source_type="rss",
                external_id="disabled",
                url="https://example.com/disabled",
                title="Disabled",
            ),
            RawItem(
                source_id="github",
                source_type="github_repo",
                external_id="issue",
                url="https://github.com/example/repo/issues/1",
                title="Old noisy issue",
                metadata={"kind": "issue"},
            ),
        ]
    )

    counts = db.prune_pending_items({"active", "github"}, {"github"}, 7)

    assert counts == {
        "stale": 1,
        "disabled_source": 1,
        "disabled_github_issue": 1,
        "deleted": 3,
    }
    with db.SessionLocal() as session:
        rows = session.scalars(select(db.ItemRow)).all()
    assert [row.external_id for row in rows] == ["fresh"]


def test_report_balances_categories_and_caps_github(monkeypatch, tmp_path):
    configure_test_database(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "report_max_items", 15)
    monkeypatch.setattr(settings, "report_per_source_max_items", 1)
    monkeypatch.setattr(settings, "report_github_max_items", 3)
    monkeypatch.setattr(settings, "report_china_min_items", 4)
    monkeypatch.setattr(settings, "report_academic_min_items", 3)
    monkeypatch.setattr(settings, "report_social_min_items", 2)

    specs = []
    specs += [(f"github-{i}", "github_repo", "GLOBAL") for i in range(7)]
    specs += [(f"china-{i}", "rss", "CN") for i in range(4)]
    specs += [(f"paper-{i}", "arxiv", "GLOBAL") for i in range(3)]
    specs += [("social-x", "x", "GLOBAL"), ("social-hn", "hackernews", "GLOBAL")]
    specs += [(f"general-{i}", "rss", "GLOBAL") for i in range(4)]

    for index, (source_id, source_type, region) in enumerate(specs):
        db.save_items(
            [
                RawItem(
                    source_id=source_id,
                    source_type=source_type,
                    external_id=f"item-{index}",
                    url=f"https://example.com/item-{index}",
                    title=f"Signal {index}",
                    region=region,
                )
            ]
        )
        with db.SessionLocal() as session:
            item_id = session.scalar(
                select(db.ItemRow.id).where(db.ItemRow.external_id == f"item-{index}")
            )
        db.save_analysis(
            item_id,
            ItemAnalysis(summary=f"Summary {index}", priority_score=100 - index),
        )

    result = render_daily()

    with db.SessionLocal() as session:
        selected = session.execute(
            select(db.ItemRow)
            .join(db.AnalysisRow, db.AnalysisRow.item_id == db.ItemRow.id)
            .join(db.ReportItemRow, db.ReportItemRow.analysis_id == db.AnalysisRow.id)
            .where(db.ReportItemRow.report_id == result.report_id)
        ).scalars().all()
    assert len(selected) == 15
    assert sum(item.source_type.startswith("github") for item in selected) <= 3
    assert sum(item.region == "CN" for item in selected) >= 4
    assert sum(item.source_type in {"arxiv", "openreview"} for item in selected) >= 3
    assert sum(item.source_type in {"x", "bluesky", "hackernews"} for item in selected) >= 2
    assert len({item.source_id for item in selected}) == len(selected)


def test_report_excludes_items_older_than_seven_days(monkeypatch, tmp_path):
    configure_test_database(monkeypatch, tmp_path)
    db.save_items(
        [
            RawItem(
                source_id="old-source",
                source_type="rss",
                external_id="old-item",
                url="https://example.com/old",
                title="Old but newly analysed",
                published_at=datetime.now(timezone.utc) - timedelta(days=8),
            )
        ]
    )
    with db.SessionLocal() as session:
        item_id = session.scalar(select(db.ItemRow.id))
    db.save_analysis(item_id, ItemAnalysis(summary="Old", priority_score=100))

    report = render_daily()

    assert "Items: 0." in report.path.read_text()
    assert "Old but newly analysed" not in report.path.read_text()
