from frontier_signal.ranking import priority_score, apply_evidence_caps
from frontier_signal.schemas import ItemAnalysis, AtomicClaim


def test_priority_score_range():
    a = ItemAnalysis(
        technical_confidence=90,
        impact_velocity=80,
        personal_relevance=95,
        earliness=85,
        source_diversity=70,
        marketing_risk=20,
        source_historical_precision=80,
    )
    assert 0 <= priority_score(a) <= 100


def test_code_claim_without_repo_is_capped():
    a = ItemAnalysis(
        technical_confidence=90,
        claims=[
            AtomicClaim(
                claim="Code was released",
                claim_type="code",
                evidence_type="official_announcement",
                evidence_urls=["https://example.com/post"],
            )
        ],
    )
    capped = apply_evidence_caps(a)
    assert capped.technical_confidence <= 55
