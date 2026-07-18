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
