from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from frontier_signal.schemas import AtomicClaim, RawItem


def test_raw_item_accepts_rfc_2822_published_date():
    item = RawItem(
        source_id="rss",
        source_type="rss",
        external_id="example",
        url="https://example.com/item",
        title="Example",
        published_at="Wed, 15 Jul 2026 14:52:43 +0000",
    )

    assert item.published_at == datetime(2026, 7, 15, 14, 52, 43, tzinfo=timezone.utc)


def test_atomic_claim_normalizes_fractional_confidence():
    claim = AtomicClaim(claim="Example", confidence_from_source_only=0.9)

    assert claim.confidence_from_source_only == 90


def test_atomic_claim_still_rejects_out_of_range_confidence():
    with pytest.raises(ValidationError):
        AtomicClaim(claim="Example", confidence_from_source_only=101)
