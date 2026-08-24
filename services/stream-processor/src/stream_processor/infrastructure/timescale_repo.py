from contracts.events import RawVibrationWindow
from psycopg import AsyncConnection


class TimescaleRawWindowRepository:
    """Walking Skeleton chunk'larını özellik tablosunda izlenebilir olarak saklar."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def save(self, window: RawVibrationWindow) -> None:
        query = """
            INSERT INTO vibration_features (
                time, machine_id, axis, snapshot_id, rms, kurtosis, crest_factor, peak,
                is_complete, chunks_received
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        async with await AsyncConnection.connect(self._dsn) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    query,
                    (
                        window.occurred_at,
                        window.machine_id,
                        window.axis,
                        window.snapshot_id,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        False,
                        1,
                    ),
                )
            await connection.commit()
