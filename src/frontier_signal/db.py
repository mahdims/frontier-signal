from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .schemas import RawItem, ItemAnalysis
from .settings import settings


class Base(DeclarativeBase):
    pass


class ItemRow(Base):
    __tablename__ = "items"
    __table_args__ = (UniqueConstraint("source_id", "external_id", name="uq_source_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(120), index=True)
    source_type: Mapped[str] = mapped_column(String(80))
    external_id: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text, index=True)
    title: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, default="")
    author_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    language: Mapped[str] = mapped_column(String(16), default="en")
    region: Mapped[str] = mapped_column(String(32), default="GLOBAL")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    visibility: Mapped[str] = mapped_column(String(32), default="public")
    analyzed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class AnalysisRow(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    analysis_json: Mapped[str] = mapped_column(Text)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    label: Mapped[str] = mapped_column(String(64), default="ROUTINE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UsageRow(Base):
    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FeedbackRow(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(Integer, index=True)
    verdict: Mapped[str] = mapped_column(String(32))
    project: Mapped[str | None] = mapped_column(String(200), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReportRow(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), default="daily", index=True)
    content: Mapped[str] = mapped_column(Text)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    includes_reported: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class ReportItemRow(Base):
    __tablename__ = "report_items"
    __table_args__ = (UniqueConstraint("report_id", "analysis_id", name="uq_report_analysis"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), index=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)


engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def canonicalize_url(url: str) -> str:
    clean = url.strip().split("#", 1)[0]
    if "?" in clean:
        base, query = clean.split("?", 1)
        kept = [
            part for part in query.split("&")
            if not part.lower().startswith(("utm_", "ref=", "source=", "spm="))
        ]
        clean = base + (("?" + "&".join(kept)) if kept else "")
    return clean.rstrip("/")


def item_hash(item: RawItem) -> str:
    blob = f"{item.title.strip().lower()}\n{item.content.strip()}".encode("utf-8", errors="ignore")
    return hashlib.sha256(blob).hexdigest()


def save_items(items: Iterable[RawItem]) -> tuple[int, int]:
    inserted = 0
    skipped = 0
    with SessionLocal() as session:
        for item in items:
            exists = session.scalar(
                select(ItemRow).where(
                    ItemRow.source_id == item.source_id,
                    ItemRow.external_id == item.external_id,
                )
            )
            if exists:
                skipped += 1
                continue

            visibility = str(item.metadata.get("visibility", "public"))
            row = ItemRow(
                source_id=item.source_id,
                source_type=item.source_type,
                external_id=item.external_id,
                url=item.url,
                canonical_url=canonicalize_url(item.url),
                title=item.title,
                content=item.content,
                author_name=item.author_name,
                language=item.language,
                region=item.region,
                published_at=item.published_at,
                retrieved_at=item.retrieved_at,
                metadata_json=json.dumps(item.metadata, ensure_ascii=False),
                content_hash=item_hash(item),
                visibility=visibility,
            )
            session.add(row)
            inserted += 1
        session.commit()
    return inserted, skipped


def pending_items(limit: int) -> list[ItemRow]:
    with SessionLocal() as session:
        rows = session.scalars(
            select(ItemRow)
            .where(ItemRow.analyzed.is_(False))
            .order_by(ItemRow.retrieved_at.asc())
            .limit(limit)
        ).all()
        return list(rows)


def prune_pending_items(
    active_source_ids: set[str],
    issue_disabled_source_ids: set[str],
    max_age_days: int = 7,
) -> dict[str, int]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    counts = {"stale": 0, "disabled_source": 0, "disabled_github_issue": 0}

    with SessionLocal() as session:
        rows = session.scalars(select(ItemRow).where(ItemRow.analyzed.is_(False))).all()
        for row in rows:
            reason = None
            metadata = json.loads(row.metadata_json or "{}")
            item_time = row.published_at or row.retrieved_at
            if item_time.tzinfo is None:
                item_time = item_time.replace(tzinfo=timezone.utc)

            if row.source_id not in active_source_ids:
                reason = "disabled_source"
            elif (
                row.source_id in issue_disabled_source_ids
                and metadata.get("kind") == "issue"
            ):
                reason = "disabled_github_issue"
            elif item_time < cutoff:
                reason = "stale"

            if reason:
                session.delete(row)
                counts[reason] += 1
        session.commit()

    counts["deleted"] = sum(counts.values())
    return counts


def save_analysis(item_id: int, analysis: ItemAnalysis) -> None:
    with SessionLocal() as session:
        row = AnalysisRow(
            item_id=item_id,
            analysis_json=analysis.model_dump_json(),
            priority_score=analysis.priority_score,
            label=analysis.recommended_label,
            created_at=datetime.now(timezone.utc),
        )
        session.add(row)
        item = session.get(ItemRow, item_id)
        if item:
            item.analyzed = True
        session.commit()


def recent_analyses(
    since: datetime, limit: int = 200, include_reported: bool = False
) -> list[tuple[ItemRow, AnalysisRow, ItemAnalysis]]:
    with SessionLocal() as session:
        query = (
            select(ItemRow, AnalysisRow)
            .join(AnalysisRow, AnalysisRow.item_id == ItemRow.id)
            .where(AnalysisRow.created_at >= since)
            .order_by(AnalysisRow.priority_score.desc())
            .limit(limit)
        )
        if not include_reported:
            reported_ids = select(ReportItemRow.analysis_id)
            query = query.where(~AnalysisRow.id.in_(reported_ids))
        pairs = session.execute(query).all()
        return [
            (item, analysis_row, ItemAnalysis.model_validate_json(analysis_row.analysis_json))
            for item, analysis_row in pairs
        ]


def pending_report(kind: str = "daily") -> ReportRow | None:
    with SessionLocal() as session:
        return session.scalar(
            select(ReportRow)
            .where(ReportRow.kind == kind, ReportRow.delivered_at.is_(None))
            .order_by(ReportRow.created_at.asc())
            .limit(1)
        )


def save_report(
    report_id: str,
    content: str,
    analysis_ids: list[int],
    includes_reported: bool = False,
    kind: str = "daily",
) -> None:
    with SessionLocal() as session:
        session.add(
            ReportRow(
                id=report_id,
                kind=kind,
                content=content,
                item_count=len(analysis_ids),
                includes_reported=includes_reported,
                created_at=datetime.now(timezone.utc),
            )
        )
        session.add_all(
            ReportItemRow(report_id=report_id, analysis_id=analysis_id)
            for analysis_id in analysis_ids
        )
        session.commit()


def mark_report_delivered(report_id: str) -> bool:
    with SessionLocal() as session:
        report = session.get(ReportRow, report_id)
        if report is None:
            return False
        if report.delivered_at is None:
            report.delivered_at = datetime.now(timezone.utc)
            session.commit()
        return True


def log_usage(task: str, model: str, input_tokens: int, output_tokens: int, cost: float) -> None:
    with SessionLocal() as session:
        session.add(UsageRow(
            task=task,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost,
            created_at=datetime.now(timezone.utc),
        ))
        session.commit()


def today_cost() -> float:
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    with SessionLocal() as session:
        rows = session.scalars(select(UsageRow).where(UsageRow.created_at >= start)).all()
        return float(sum(r.estimated_cost_usd for r in rows))
