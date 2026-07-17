from __future__ import annotations
from .schemas import ItemAnalysis


def priority_score(a: ItemAnalysis, duplication_penalty: float = 0.0) -> float:
    score = (
        0.32 * a.personal_relevance
        + 0.18 * a.earliness
        + 0.17 * a.technical_confidence
        + 0.13 * a.impact_velocity
        + 0.10 * a.source_diversity
        + 0.10 * a.source_historical_precision
        - 0.10 * a.marketing_risk
        - duplication_penalty
    )
    return round(max(0.0, min(100.0, score)), 2)


def apply_evidence_caps(a: ItemAnalysis) -> ItemAnalysis:
    claim_types = {c.claim_type for c in a.claims}
    evidence_types = {c.evidence_type for c in a.claims}
    urls = {u for c in a.claims for u in c.evidence_urls}

    if "code" in claim_types and not any("github.com" in u or "gitlab.com" in u for u in urls):
        a.technical_confidence = min(a.technical_confidence, 55)

    if evidence_types and evidence_types <= {"official_announcement", "social_post", "technical_media"}:
        a.technical_confidence = min(a.technical_confidence, 65)

    if not urls:
        a.source_diversity = min(a.source_diversity, 15)

    return a
