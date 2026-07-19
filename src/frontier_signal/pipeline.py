from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from .config import load_organizations, load_topics
from .db import ItemRow, pending_items, save_analysis
from .llm import DeepSeekGateway, read_prompt, BudgetExceeded
from .ranking import apply_evidence_caps, priority_score
from .schemas import ItemAnalysis, TranslationResult, ExtractionResult, ImpactResult, SkepticResult
from .settings import settings


def bounded_content(content: str, limit: int) -> str:
    if re.search(r"</?(?:article|div|figure|img|p|section|span)\b", content, re.I):
        content = BeautifulSoup(content, "html.parser").get_text(" ", strip=True)
    return " ".join(content.split())[:limit]


def row_payload(row: ItemRow, content_limit: int | None = None) -> dict:
    content_limit = content_limit if content_limit is not None else settings.max_llm_content_chars
    return {
        "item_id": row.id,
        "source_id": row.source_id,
        "source_type": row.source_type,
        "url": row.url,
        "title": row.title,
        "content": bounded_content(row.content, content_limit) if content_limit else "",
        "author_name": row.author_name,
        "language": row.language,
        "region": row.region,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "retrieved_at": row.retrieved_at.isoformat(),
        "metadata": json.loads(row.metadata_json or "{}"),
    }


def analyze_one(row: ItemRow, gateway: DeepSeekGateway) -> ItemAnalysis:
    item_context = row_payload(row, content_limit=0)
    analysis = ItemAnalysis()
    trace: dict = {}

    working_title = row.title
    working_content = bounded_content(row.content, settings.max_llm_content_chars)

    if row.language.lower() not in {"en", "eng"}:
        translated = gateway.call_json(
            "translate",
            read_prompt("translate"),
            {
                "item": row_payload(
                    row, content_limit=settings.max_translation_content_chars
                ),
                "organization_aliases": load_organizations(),
            },
            TranslationResult,
        )
        analysis.translated_title = translated.translated_title
        analysis.translated_content = translated.translated_content
        working_title = translated.translated_title
        working_content = translated.translated_content[: settings.max_llm_content_chars]
        trace["translation_model"] = settings.deepseek_flash_model

    extraction = gateway.call_json(
        "extract",
        read_prompt("extract"),
        {
            "item": item_context,
            "working_title": working_title,
            "working_content": working_content,
        },
        ExtractionResult,
    )
    analysis.summary = extraction.summary
    analysis.claims = extraction.claims[:5]
    analysis.entities = extraction.entities[:10]
    analysis.topics = extraction.topics[:10]
    analysis.promotional_phrases = extraction.promotional_phrases[:5]
    analysis.missing_evidence = extraction.missing_evidence[:5]
    trace["extraction_model"] = settings.deepseek_flash_model

    impact = gateway.call_json(
        "impact",
        read_prompt("impact"),
        {
            "item": item_context,
            "analysis": {
                "summary": analysis.summary,
                "claims": [claim.model_dump() for claim in analysis.claims],
                "entities": analysis.entities,
                "topics": analysis.topics,
                "promotional_phrases": analysis.promotional_phrases,
                "missing_evidence": analysis.missing_evidence,
            },
            "user_ontology": load_topics(),
        },
        ImpactResult,
    )
    for field in (
        "technical_confidence", "impact_velocity", "personal_relevance", "earliness",
        "source_diversity", "marketing_risk", "source_historical_precision",
        "recommended_label", "rationale", "verification_actions",
    ):
        setattr(analysis, field, getattr(impact, field))
    trace["impact_model"] = settings.deepseek_flash_model

    analysis = apply_evidence_caps(analysis)
    analysis.priority_score = priority_score(analysis)

    should_skeptic = (
        analysis.priority_score >= settings.pro_priority_threshold
        or analysis.marketing_risk >= 65
    )
    if should_skeptic:
        skeptic = gateway.call_json(
            "skeptic",
            read_prompt("skeptic"),
            {
                "item": item_context,
                "analysis": analysis.model_dump(exclude={"translated_content"}),
            },
            SkepticResult,
        )
        analysis.skeptic_objections = skeptic.strongest_objections
        analysis.technical_confidence = max(
            0, min(100, analysis.technical_confidence + skeptic.confidence_adjustment)
        )
        analysis.marketing_risk = max(
            0, min(100, analysis.marketing_risk + skeptic.marketing_risk_adjustment)
        )
        analysis.priority_score = priority_score(analysis)
        trace["skeptic_model"] = settings.deepseek_pro_model

    analysis.model_trace = trace
    return analysis


def analyze_pending(limit: int | None = None) -> tuple[int, int]:
    limit = min(
        limit or settings.max_items_analyzed_per_run,
        settings.max_items_analyzed_per_run,
    )
    gateway = DeepSeekGateway()
    successes = 0
    failures = 0
    for row in pending_items(limit):
        try:
            analysis = analyze_one(row, gateway)
            save_analysis(row.id, analysis)
            successes += 1
        except BudgetExceeded:
            break
        except Exception as exc:
            failures += 1
            print(f"[analysis-error] item={row.id} source={row.source_id}: {exc}")
    return successes, failures
