from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from .db import pending_report, recent_analyses, save_report
from .settings import settings


@dataclass(frozen=True)
class ReportResult:
    report_id: str
    path: Path
    reused_pending: bool


def safe_public_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _write_report_files(report_id: str, content: str, created_at: datetime) -> Path:
    out_dir = settings.output_dir / "daily"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{created_at.date().isoformat()}-{report_id}.md"
    path.write_text(content, encoding="utf-8")
    (out_dir / "latest.json").write_text(
        json.dumps({"report_id": report_id, "path": str(path)}),
        encoding="utf-8",
    )
    return path


def render_daily(hours: int = 30, include_reported: bool = False) -> ReportResult:
    if not include_reported:
        existing = pending_report()
        if existing is not None:
            path = _write_report_files(existing.id, existing.content, existing.created_at)
            return ReportResult(existing.id, path, reused_pending=True)

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    pairs = recent_analyses(since, limit=300, include_reported=include_reported)

    selected = []
    for item, analysis_row, analysis in pairs:
        if len(selected) >= settings.report_max_items:
            break
        if item.visibility != "public" and not settings.share_private_items:
            continue
        if not safe_public_url(item.url):
            continue
        selected.append((item, analysis_row.id, analysis))

    now = datetime.now(timezone.utc)

    lines = [
        f"# Frontier Signal Daily Radar — {now.date().isoformat()}",
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
        [analysis_id for _, analysis_id, _ in selected],
        includes_reported=include_reported,
    )
    path = _write_report_files(report_id, content, now)
    return ReportResult(report_id, path, reused_pending=False)
