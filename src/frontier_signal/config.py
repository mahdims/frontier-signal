from __future__ import annotations

from pathlib import Path
import yaml

from .schemas import SourceConfig
from .settings import settings


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_sources() -> list[SourceConfig]:
    data = load_yaml(settings.config_dir / "sources.yaml")
    return [SourceConfig.model_validate(x) for x in data.get("sources", [])]


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
