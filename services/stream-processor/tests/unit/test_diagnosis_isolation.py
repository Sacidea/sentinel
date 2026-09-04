"""Teshis katmani canli boruya sizmamali (ADR-0015 kapandi)."""

from pathlib import Path

import pytest
from stream_processor.application import snapshot_pipeline
from stream_processor.domain import features


@pytest.mark.unit
def test_snapshot_pipeline_does_not_import_diagnosis() -> None:
    text = Path(snapshot_pipeline.__file__).read_text(encoding="utf-8")
    assert "domain.diagnosis" not in text
    assert "diagnose_prominence" not in text
    assert "fault_type" not in text


@pytest.mark.unit
def test_feature_extraction_does_not_import_diagnosis() -> None:
    text = Path(features.__file__).read_text(encoding="utf-8")
    assert "domain.diagnosis" not in text
    assert "diagnose_prominence" not in text
