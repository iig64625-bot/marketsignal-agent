"""Tests for the YAML pipeline configuration loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from signalpulse.config.loader import (
    CompetitorConfig,
    PipelineConfig,
    SourceConfig,
    TargetConfig,
    load_pipeline_config,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_CONFIG = REPO_ROOT / "configs" / "competitors.ai-agent.yaml"


def test_load_real_config():
    """The shipped ``ai-agent`` config parses into a populated PipelineConfig."""
    cfg = load_pipeline_config(SAMPLE_CONFIG)
    assert isinstance(cfg, PipelineConfig)
    assert cfg.target.name == "Dify"
    assert cfg.target.website == "https://dify.ai"
    assert [c.name for c in cfg.competitors] == ["Coze", "FastGPT"]
    assert cfg.time_window_days == 7
    assert cfg.generate_weekly_report is True
    assert cfg.generate_battlecards is True
    assert cfg.run_evals is True


def test_load_config_extracts_source_types():
    """Each competitor's sources are typed and routed to the right fetcher family."""
    cfg = load_pipeline_config(SAMPLE_CONFIG)
    coze = cfg.competitors[0]
    assert isinstance(coze, CompetitorConfig)
    assert {s.type for s in coze.sources} == {"changelog", "website", "jobs", "github"}
    assert all(isinstance(s, SourceConfig) for s in coze.sources)


def test_load_minimal_yaml(tmp_path: Path):
    """A minimal config without optional sections still works."""
    yaml = tmp_path / "mini.yaml"
    yaml.write_text(
        "target_company:\n  name: Mini\n  website: https://mini.test\n"
        "competitors:\n  - name: Tiny\n    website: https://tiny.test\n    sources: []\n",
        encoding="utf-8",
    )
    cfg = load_pipeline_config(yaml)
    assert isinstance(cfg.target, TargetConfig)
    assert cfg.target.description == ""
    assert cfg.competitors[0].sources == []
    assert cfg.monitoring_dimensions == []


def test_missing_target_raises(tmp_path: Path):
    """A config without ``target_company`` is rejected with ``KeyError``."""
    yaml = tmp_path / "bad.yaml"
    yaml.write_text("competitors: []\n", encoding="utf-8")
    with pytest.raises(KeyError):
        load_pipeline_config(yaml)
