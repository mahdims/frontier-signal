from __future__ import annotations

from pathlib import Path
import yaml

from .schemas import SourceConfig
from .settings import settings


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_sources() -> list[SourceConfig]:
    entries: list[dict] = []
    for filename in ("sources.yaml", "china_sources.yaml"):
        path = settings.config_dir / filename
        if path.exists():
            entries.extend(load_yaml(path).get("sources", []))

    sources = [SourceConfig.model_validate(entry) for entry in entries]
    ids = [source.id for source in sources]
    duplicates = sorted({source_id for source_id in ids if ids.count(source_id) > 1})
    if duplicates:
        raise ValueError(f"Duplicate source IDs: {', '.join(duplicates)}")
    return sources


def source_by_id(source_id: str) -> SourceConfig:
    for source in load_sources():
        if source.id == source_id:
            return source
    raise KeyError(f"Unknown source: {source_id}")


def load_topics() -> dict:
    return load_yaml(settings.config_dir / "topics.yaml").get("topics", {})


def load_organizations() -> list[dict]:
    return load_yaml(settings.config_dir / "organizations.yaml").get("organizations", [])


def load_model_routing() -> dict:
    return load_yaml(settings.config_dir / "model_routing.yaml")
