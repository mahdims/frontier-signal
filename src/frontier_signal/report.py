from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from .db import recent_analyses
from .settings import settings


def safe_public_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def render_daily(hours: int = 30) -> Path:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    pairs = recent_analyses(since, limit=300)

    selected = []
    for item, analysis in pairs:
        if len(selected) >= settings.report_max_items:
            break
        if item.visibility != "public" and not settings.share_private_items:
            continue
        if not safe_public_url(item.url):
            continue
        selected.append((item, analysis))

    now = datetime.now(timezone.utc)
    out_dir = settings.output_dir / "daily"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{now.date().isoformat()}.md"

    lines = [
        f"# Frontier Signal Daily Radar — {now.date().isoformat()}",
        "",
        f"Window: previous {hours} hours. Items: {len(selected)}.",
        "",
        "Scores are separate: technical confidence is not social impact.",
        "",
    ]

    for rank, (item, a) in enumerate(selected, start=1):
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

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
