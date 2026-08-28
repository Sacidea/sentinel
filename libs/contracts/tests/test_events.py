from datetime import UTC, datetime
from uuid import uuid4

import pytest
from contracts.events import ANOMALY_SCHEMA_VERSION, AnomalyDetected


def _base(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "event_id": uuid4(),
        "occurred_at": datetime(2004, 2, 12, 10, 32, 39, tzinfo=UTC),
        "machine_id": "bearing_1",
        "axis": "x",
        "metric": "rms",
        "value": 0.3,
        "severity": "warning",
        "is_complete": True,
        "detector": "zscore",
        "score_kind": "zscore",
        "z_score": 6.0,
    }
    payload.update(overrides)
    return payload


@pytest.mark.unit
def test_layer1_keeps_z_score_and_schema_v2() -> None:
    event = AnomalyDetected.model_validate(_base())
    assert event.schema_version == ANOMALY_SCHEMA_VERSION
    assert event.z_score == pytest.approx(6.0)
    assert event.anomaly_score is None
    assert event.score_kind == "zscore"
    assert event.reported_score() == pytest.approx(6.0)


@pytest.mark.unit
def test_isolation_forest_uses_anomaly_score_not_z_score() -> None:
    event = AnomalyDetected.model_validate(
        _base(
            detector="isolation_forest",
            metric="feature_vector",
            z_score=None,
            anomaly_score=0.014,
            score_kind="if_score",
        )
    )
    assert event.z_score is None
    assert event.anomaly_score == pytest.approx(0.014)
    assert event.score_kind == "if_score"
    assert event.reported_score() == pytest.approx(0.014)


@pytest.mark.unit
def test_extent_kind_does_not_reuse_z_score() -> None:
    event = AnomalyDetected.model_validate(
        _base(
            detector="isolation_forest",
            metric="feature_vector",
            z_score=None,
            anomaly_score=8.65,
            score_kind="extent",
        )
    )
    assert event.z_score is None
    assert event.score_kind == "extent"
    assert event.reported_score() == pytest.approx(8.65)


@pytest.mark.unit
def test_v1_payload_infers_score_kind_zscore() -> None:
    payload = _base()
    del payload["score_kind"]
    payload["schema_version"] = 1
    event = AnomalyDetected.model_validate(payload)
    assert event.score_kind == "zscore"
    assert event.schema_version == 1
    assert event.z_score == pytest.approx(6.0)


@pytest.mark.unit
def test_v1_kafka_json_without_new_fields_parses() -> None:
    """Canli topic'te kalan v1 govde: anomaly_score/score_kind anahtari yok."""
    event_id = uuid4()
    payload = {
        "event_id": str(event_id),
        "occurred_at": "2004-02-12T10:32:39Z",
        "machine_id": "bearing_1",
        "axis": "x",
        "metric": "rms",
        "value": 0.3,
        "z_score": 6.0,
        "severity": "warning",
        "is_complete": True,
        "detector": "zscore",
        "schema_version": 1,
    }
    event = AnomalyDetected.model_validate(payload)
    assert event.event_id == event_id
    assert event.anomaly_score is None
    assert event.score_kind == "zscore"
    assert event.reported_score() == pytest.approx(6.0)


@pytest.mark.unit
def test_v1_isolation_forest_keeps_score_in_z_score_field() -> None:
    """v1 IF skoru z_score'a yazilmisti; parse kirilmamali, skor oradan okunur."""
    event = AnomalyDetected.model_validate(
        {
            "event_id": uuid4(),
            "occurred_at": datetime(2004, 2, 12, 10, 32, 39, tzinfo=UTC),
            "machine_id": "bearing_3",
            "axis": "x",
            "metric": "feature_vector",
            "value": 0.014,
            "z_score": 0.014,
            "severity": "warning",
            "is_complete": True,
            "detector": "isolation_forest",
            "schema_version": 1,
        }
    )
    assert event.anomaly_score is None
    assert event.score_kind == "if_score"
    assert event.reported_score() == pytest.approx(0.014)
