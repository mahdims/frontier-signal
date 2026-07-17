from __future__ import annotations

from rapidfuzz.fuzz import token_set_ratio
from sqlalchemy import select

from .db import SessionLocal, ItemRow


def find_duplicate(item: ItemRow, title_threshold: int = 94) -> ItemRow | None:
    with SessionLocal() as session:
        exact = session.scalar(
            select(ItemRow).where(
                ItemRow.id != item.id,
                (ItemRow.canonical_url == item.canonical_url) | (ItemRow.content_hash == item.content_hash),
            )
        )
        if exact:
            return exact

        recent = session.scalars(
            select(ItemRow)
            .where(ItemRow.id != item.id)
            .order_by(ItemRow.retrieved_at.desc())
            .limit(500)
        ).all()
        for other in recent:
            if token_set_ratio(item.title, other.title) >= title_threshold:
                return other
    return None
