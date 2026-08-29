import os
import random
from collections.abc import AsyncGenerator, Sequence
from datetime import UTC, datetime, timedelta
from typing import Literal

import structlog

from simulator.ports.dataset import DatasetProvider

logger = structlog.get_logger(__name__)

Axis = Literal["x", "y"]
Channel = tuple[str, Axis]
SnapshotRow = tuple[str, Axis, list[float], datetime]

# Sütun sayısı = kanal sayısı. Set numarası yok: 4 tek eksen, 8 çift eksen.
_CHANNELS_BY_WIDTH: dict[int, tuple[Channel, ...]] = {
    4: (
        ("bearing_1", "x"),
        ("bearing_2", "x"),
        ("bearing_3", "x"),
        ("bearing_4", "x"),
    ),
    8: (
        ("bearing_1", "x"),
        ("bearing_1", "y"),
        ("bearing_2", "x"),
        ("bearing_2", "y"),
        ("bearing_3", "x"),
        ("bearing_3", "y"),
        ("bearing_4", "x"),
        ("bearing_4", "y"),
    ),
}


def channels_for_width(width: int) -> tuple[Channel, ...] | None:
    """4 → Set 2 tek eksen; 8 → Set 1 x/y. Başka genişlik yok."""
    return _CHANNELS_BY_WIDTH.get(width)


def parse_sample_row(parts: Sequence[str], width: int) -> list[float] | None:
    """Beklenen sütun sayısı tutmazsa veya float değilse satır atlanır."""
    if len(parts) != width:
        return None
    try:
        return [float(part) for part in parts]
    except ValueError:
        return None


class LocalDatasetAdapter(DatasetProvider):
    """
    Belirtilen klasördeki NASA IMS dosyalarını okuyan,
    klasör/dosya yoksa rastgele sentetik veri üreten adaptör.
    """

    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path
        self._is_synthetic = not self._has_dataset_files(dataset_path)
        if self._is_synthetic:
            logger.warning(
                "Dataset bulunamadı; sentetik veri moduna geçiliyor.", dataset_path=dataset_path
            )

    @staticmethod
    def _has_dataset_files(dataset_path: str) -> bool:
        """Boş bir klasör de 'veri yok' sayılır; aksi halde simülatör hemen sonlanır."""
        if not os.path.isdir(dataset_path):
            return False
        return any(entry.is_file() for entry in os.scandir(dataset_path))

    async def stream_snapshots(
        self,
    ) -> AsyncGenerator[list[SnapshotRow], None]:
        if self._is_synthetic:
            async for snapshot in self._generate_synthetic():
                yield snapshot
        else:
            async for snapshot in self._read_from_disk():
                yield snapshot

    async def _generate_synthetic(
        self,
    ) -> AsyncGenerator[list[SnapshotRow], None]:
        """Sonsuz sentetik gürültü üretir."""
        current_time = datetime.now(UTC)
        while True:
            snapshot = []
            for i in range(1, 5):  # 4 bearing
                machine_id = f"bearing_{i}"
                axis: Axis = "x"
                # 20480 noktalık rastgele beyaz gürültü (-1.0 ile 1.0 arası)
                samples = [random.uniform(-1.0, 1.0) for _ in range(20480)]
                snapshot.append((machine_id, axis, samples, current_time))

            yield snapshot
            current_time += timedelta(minutes=10)  # NASA IMS 10 dakikada bir ölçüm alır

    async def _read_from_disk(
        self,
    ) -> AsyncGenerator[list[SnapshotRow], None]:
        """Gerçek dosyaları tarih sırasına göre okur. Sütun sayısı dosyadan algılanır."""
        files = sorted(os.listdir(self.dataset_path))
        for filename in files:
            filepath = os.path.join(self.dataset_path, filename)
            if not os.path.isfile(filepath):
                continue

            # Dosya adı formatı genelde: 2003.10.22.12.06.24 (Y.m.d.H.M.S)
            # TIMESTAMPTZ kolonuna gittiği için naive değer bırakılmaz; UTC olarak işaretlenir.
            try:
                source_timestamp = datetime.strptime(filename, "%Y.%m.%d.%H.%M.%S").replace(
                    tzinfo=UTC
                )
            except ValueError:
                source_timestamp = datetime.now(UTC)

            snapshot = self._snapshot_from_file(filepath, source_timestamp)
            if snapshot is None:
                logger.warning("IMS dosyası atlandı (4/8 sütunlu satır yok).", file=filename)
                continue
            yield snapshot

    def _snapshot_from_file(
        self, filepath: str, source_timestamp: datetime
    ) -> list[SnapshotRow] | None:
        columns: list[list[float]] | None = None
        layout: tuple[Channel, ...] | None = None
        with open(filepath) as handle:
            for line in handle:
                parts = line.strip().split()
                if not parts:
                    continue
                if layout is None:
                    layout = channels_for_width(len(parts))
                    if layout is None:
                        continue
                    probe = parse_sample_row(parts, len(layout))
                    if probe is None:
                        layout = None
                        continue
                    columns = [[] for _ in layout]
                    for index, value in enumerate(probe):
                        columns[index].append(value)
                    continue
                values = parse_sample_row(parts, len(layout))
                if values is None or columns is None:
                    continue
                for index, value in enumerate(values):
                    columns[index].append(value)

        if layout is None or columns is None or not columns[0]:
            return None
        return [
            (machine_id, axis, columns[index], source_timestamp)
            for index, (machine_id, axis) in enumerate(layout)
        ]
