from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from dateutil.parser import parse as parse_datetime
from pydantic import BaseModel, Field, field_validator


class SourceConfig(BaseModel):
    id: str
    name: str
    type: str
    enabled: bool = True
    region: str = "GLOBAL"
    language: str = "en"
    homepage: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class RawItem(BaseModel):
    source_id: str
    source_type: str
    external_id: str
    url: str
    title: str
    content: str = ""
    author_name: str | None = None
    language: str = "en"
    region: str = "GLOBAL"
    published_at: datetime | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("published_at", "retrieved_at", mode="before")
    @classmethod
    def parse_flexible_datetime(cls, value: Any) -> Any:
        """Accept RFC 2822 dates commonly returned by RSS feeds."""
        if isinstance(value, str):
            return parse_datetime(value)
        return value


class AtomicClaim(BaseModel):
    claim: str
    claim_type: str = "other"
    attribution: str = ""
    evidence_type: str = "other"
    confidence_from_source_only: int = Field(default=50, ge=0, le=100)
    requires_verification: bool = True
    evidence_urls: list[str] = Field(default_factory=list)

    @field_validator("confidence_from_source_only", mode="before")
    @classmethod
    def normalize_fractional_confidence(cls, value: Any) -> Any:
        """Normalize model-produced 0-1 confidence fractions to 0-100 integers."""
        if isinstance(value, float) and 0 <= value <= 1:
            return round(value * 100)
        return value


class ItemAnalysis(BaseModel):
    translated_title: str | None = None
    translated_content: str | None = None
    summary: str = ""
    claims: list[AtomicClaim] = Field(default_factory=list)
    entities: list[dict[str, Any]] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    promotional_phrases: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)

    technical_confidence: int = Field(default=50, ge=0, le=100)
    impact_velocity: int = Field(default=0, ge=0, le=100)
    personal_relevance: int = Field(default=0, ge=0, le=100)
    earliness: int = Field(default=50, ge=0, le=100)
    source_diversity: int = Field(default=0, ge=0, le=100)
    marketing_risk: int = Field(default=50, ge=0, le=100)
    source_historical_precision: int = Field(default=50, ge=0, le=100)

    recommended_label: str = "ROUTINE"
    rationale: dict[str, str] = Field(default_factory=dict)
    verification_actions: list[str] = Field(default_factory=list)
    skeptic_objections: list[dict[str, Any]] = Field(default_factory=list)
    priority_score: float = 0.0
    model_trace: dict[str, Any] = Field(default_factory=dict)


class TranslationResult(BaseModel):
    translated_title: str
    translated_content: str
    detected_language: str
    canonical_entities: list[dict[str, Any]] = Field(default_factory=list)
    translation_notes: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    summary: str
    claims: list[AtomicClaim]
    entities: list[dict[str, Any]] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    promotional_phrases: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


class ImpactResult(BaseModel):
    technical_confidence: int = Field(ge=0, le=100)
    impact_velocity: int = Field(ge=0, le=100)
    personal_relevance: int = Field(ge=0, le=100)
    earliness: int = Field(ge=0, le=100)
    source_diversity: int = Field(ge=0, le=100)
    marketing_risk: int = Field(ge=0, le=100)
    source_historical_precision: int = Field(default=50, ge=0, le=100)
    rationale: dict[str, str]
    recommended_label: str
    verification_actions: list[str] = Field(default_factory=list)


class SkepticResult(BaseModel):
    strongest_objections: list[dict[str, Any]] = Field(default_factory=list)
    surviving_claims: list[str] = Field(default_factory=list)
    confidence_adjustment: int = Field(default=0, ge=-50, le=20)
    marketing_risk_adjustment: int = Field(default=0, ge=-20, le=50)
    final_assessment: str = ""
