from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlparse
from uuid import uuid4
from zoneinfo import ZoneInfo

from .db import AnalysisRow, ItemRow, pending_report, recent_analyses, save_report
from .schemas import ItemAnalysis
from .settings import settings


@dataclass(frozen=True)
class ReportResult:
    report_id: str
    path: Path
    email_path: Path
    reused_pending: bool


def safe_public_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _local_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo(settings.report_timezone))


def _email_digest(content: str) -> str:
    """Turn the archived full report into a compact email-friendly digest."""
    lines = content.splitlines()
    output = lines[:1] + [""]
    window = next((line for line in lines if line.startswith("Window:")), "")
    if window:
        output += [window, "", "The full analysis is attached.", ""]

    starts = [index for index, line in enumerate(lines) if re.match(r"^## \d+\. ", line)]
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        section = lines[start:end]
        output += [section[0], ""]
        label = next((line for line in section if line.startswith("**Label:**")), "")
        if label:
            output += [label, ""]
            label_index = section.index(label)
            summary_lines = []
            for line in section[label_index + 1 :]:
                if line == "**Why this matters**":
                    break
                if line.strip():
                    summary_lines.append(line)
            if summary_lines:
                output += [" ".join(summary_lines), ""]
    return "\n".join(output).rstrip() + "\n"


def _write_report_files(
    report_id: str, content: str, created_at: datetime
) -> tuple[Path, Path]:
    out_dir = settings.output_dir / "daily"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_date = _local_datetime(created_at).date().isoformat()
    path = out_dir / f"{report_date}-{report_id}.md"
    email_path = out_dir / f"{report_date}-{report_id}.email.md"
    path.write_text(content, encoding="utf-8")
    email_path.write_text(_email_digest(content), encoding="utf-8")
    (out_dir / "latest.json").write_text(
        json.dumps(
            {
                "report_id": report_id,
                "path": str(path),
                "email_path": str(email_path),
                "date": report_date,
            }
        ),
        encoding="utf-8",
    )
    return path, email_path


ReportPair = tuple[ItemRow, AnalysisRow, ItemAnalysis]


def _is_fresh(item: ItemRow, now: datetime) -> bool:
    item_time = item.published_at or item.retrieved_at
    if item_time.tzinfo is None:
        item_time = item_time.replace(tzinfo=timezone.utc)
    return now - timedelta(days=settings.max_item_age_days) <= item_time <= now + timedelta(days=1)


def _select_balanced(pairs: list[ReportPair], now: datetime) -> list[ReportPair]:
    eligible = [
        pair
        for pair in pairs
        if (pair[0].visibility == "public" or settings.share_private_items)
        and safe_public_url(pair[0].url)
        and _is_fresh(pair[0], now)
    ]
    selected: list[ReportPair] = []
    selected_ids: set[int] = set()
    source_counts: dict[str, int] = {}
    github_count = 0

    def add(pair: ReportPair) -> bool:
        nonlocal github_count
        item, analysis_row, _ = pair
        is_github = item.source_type in {"github_repo", "github_org"}
        if analysis_row.id in selected_ids or len(selected) >= settings.report_max_items:
            return False
        if source_counts.get(item.source_id, 0) >= settings.report_per_source_max_items:
            return False
        if is_github and github_count >= settings.report_github_max_items:
            return False
        selected.append(pair)
        selected_ids.add(analysis_row.id)
        source_counts[item.source_id] = source_counts.get(item.source_id, 0) + 1
        github_count += int(is_github)
        return True

    def reserve(predicate, minimum: int) -> None:
        current = sum(1 for pair in selected if predicate(pair[0]))
        for pair in eligible:
            if current >= minimum or len(selected) >= settings.report_max_items:
                break
            if predicate(pair[0]) and add(pair):
                current += 1

    reserve(
        lambda item: item.region.upper() == "CN"
        and item.source_type not in {"github_repo", "github_org"},
        settings.report_china_min_items,
    )
    reserve(
        lambda item: item.source_type in {"arxiv", "openreview"},
        settings.report_academic_min_items,
    )
    reserve(
        lambda item: item.source_type in {"x", "bluesky", "hackernews"},
        settings.report_social_min_items,
    )
    for pair in eligible:
        if len(selected) >= settings.report_max_items:
            break
        add(pair)
    return sorted(selected, key=lambda pair: pair[1].priority_score, reverse=True)


def render_daily(hours: int = 30, include_reported: bool = False) -> ReportResult:
    if not include_reported:
        existing = pending_report()
        if existing is not None:
            path, email_path = _write_report_files(
                existing.id, existing.content, existing.created_at
            )
            return ReportResult(existing.id, path, email_path, reused_pending=True)

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    pairs = recent_analyses(since, limit=300, include_reported=include_reported)

    now = datetime.now(timezone.utc)
    selected = _select_balanced(pairs, now)
    local_now = _local_datetime(now)

    lines = [
        f"# Frontier Signal Daily Radar — {local_now.date().isoformat()}",
        "",
        f"Window: previous {hours} hours. Items: {len(selected)}.",
        "",
        "Scores are separate: technical confidence is not social impact.",
        "",
    ]

    for rank, (item, _, a) in enumerate(selected, start=1):
        title = a.translated_title or item.title
        lines += [
            f"## {rank}. [{title}]({item.url})",
            "",
        ]
        if a.translated_title and a.translated_title != item.title:
            lines += [f"**Original title:** {item.title}", ""]
        lines += [
            f"**Label:** `{a.recommended_label}` · **Priority:** {a.priority_score:.1f}/100",
            "",
            a.summary or "_No summary available._",
            "",
            "**Why this matters**",
            "",
            a.rationale.get("personal_relevance", "Not provided."),
            "",
            "**Scores**",
            "",
            "| Technical confidence | Impact velocity | Personal relevance | Earliness | Source diversity | Marketing risk |",
            "|---:|---:|---:|---:|---:|---:|",
            f"| {a.technical_confidence} | {a.impact_velocity} | {a.personal_relevance} | {a.earliness} | {a.source_diversity} | {a.marketing_risk} |",
            "",
        ]
        if a.claims:
            lines += ["**Atomic claims**", ""]
            for c in a.claims[:5]:
                lines.append(f"- {c.claim} _(source confidence: {c.confidence_from_source_only}/100)_")
                for url in c.evidence_urls[:3]:
                    if safe_public_url(url):
                        lines.append(f"  - Evidence: {url}")
            lines.append("")
        if a.skeptic_objections:
            lines += ["**Skeptic objections**", ""]
            for objection in a.skeptic_objections[:4]:
                lines.append(
                    f"- **{objection.get('severity', 'unknown')}** — {objection.get('objection', '')}"
                )
            lines.append("")
        if a.verification_actions:
            lines += ["**Next verification actions**", ""]
            for action in a.verification_actions[:4]:
                lines.append(f"- {action}")
            lines.append("")
        lines += [
            f"**Original source:** {item.url}",
            "",
            "---",
            "",
        ]

    content = "\n".join(lines)
    report_id = str(uuid4())
    save_report(
        report_id,
        content,
        [analysis_row.id for _, analysis_row, _ in selected],
        includes_reported=include_reported,
    )
    path, email_path = _write_report_files(report_id, content, now)
    return ReportResult(report_id, path, email_path, reused_pending=False)
