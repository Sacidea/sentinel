from contracts.events import AnomalyDetected, VibrationFeatures
from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from stream_processor.domain.detectors import BaselineSnapshot


class TimescaleRepository:
    """Özellikleri ve anomali olaylarını TimescaleDB'ye yazar; ham örnek yazılmaz."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def save_features(self, features: VibrationFeatures) -> None:
        query = """
            INSERT INTO vibration_features (
                time, machine_id, axis, snapshot_id, rms, kurtosis, crest_factor, peak,
                fft_band_energy, is_complete, chunks_received
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        async with await AsyncConnection.connect(self._dsn) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    query,
                    (
                        features.occurred_at,
                        features.machine_id,
                        features.axis,
                        features.snapshot_id,
                        features.rms,
                        features.kurtosis,
                        features.crest_factor,
                        features.peak,
                        Jsonb(features.fft_band_energy),
                        features.is_complete,
                        features.chunks_received,
                    ),
                )
            await connection.commit()

    async def save_anomaly(self, event: AnomalyDetected) -> None:
        query = """
            INSERT INTO anomaly_events (
                event_id, occurred_at, machine_id, axis, metric, value, z_score,
                anomaly_score, score_kind, severity, is_complete, detector
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO NOTHING
        """
        async with await AsyncConnection.connect(self._dsn) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    query,
                    (
                        event.event_id,
                        event.occurred_at,
                        event.machine_id,
                        event.axis,
                        event.metric,
                        event.value,
                        event.z_score,
                        event.anomaly_score,
                        event.score_kind,
                        event.severity,
                        event.is_complete,
                        event.detector,
                    ),
                )
            await connection.commit()

    async def save_baseline(self, snapshot: BaselineSnapshot) -> None:
        query = """
            INSERT INTO machine_baseline (machine_id, axis, metric, mean, std, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (machine_id, axis, metric) DO NOTHING
        """
        async with await AsyncConnection.connect(self._dsn) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    query,
                    (
                        snapshot.machine_id,
                        snapshot.axis,
                        snapshot.metric,
                        snapshot.mean,
                        snapshot.std,
                    ),
                )
            await connection.commit()

    async def load_baselines(self) -> list[BaselineSnapshot]:
        query = """
            SELECT machine_id, axis, metric, mean, std
            FROM machine_baseline
            WHERE mean IS NOT NULL AND std IS NOT NULL
        """
        async with (
            await AsyncConnection.connect(self._dsn) as connection,
            connection.cursor() as cursor,
        ):
            await cursor.execute(query)
            rows = await cursor.fetchall()
        snapshots: list[BaselineSnapshot] = []
        for machine_id, axis, metric, mean, std in rows:
            if metric not in ("rms", "kurtosis"):
                continue
            snapshots.append(
                BaselineSnapshot(
                    machine_id=str(machine_id),
                    axis=str(axis),
                    metric=metric,
                    mean=float(mean),
                    std=float(std),
                )
            )
        return snapshots
