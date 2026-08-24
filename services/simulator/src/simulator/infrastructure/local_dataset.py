import os
import random
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Literal

import structlog

from simulator.ports.dataset import DatasetProvider

logger = structlog.get_logger(__name__)


class LocalDatasetAdapter(DatasetProvider):
    """
    Belirtilen klasördeki NASA IMS dosyalarını okuyan,
    klasör/dosya yoksa rastgele sentetik veri üreten adaptör.
    """

    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path
        self._is_synthetic = not os.path.exists(dataset_path) or not os.path.isdir(dataset_path)
        if self._is_synthetic:
            logger.warning(
                "Dataset bulunamadı; sentetik veri moduna geçiliyor.", dataset_path=dataset_path
            )

    async def stream_snapshots(
        self,
    ) -> AsyncGenerator[list[tuple[str, Literal["x", "y"], list[float], datetime]], None]:
        if self._is_synthetic:
            async for snapshot in self._generate_synthetic():
                yield snapshot
        else:
            async for snapshot in self._read_from_disk():
                yield snapshot

    async def _generate_synthetic(
        self,
    ) -> AsyncGenerator[list[tuple[str, Literal["x", "y"], list[float], datetime]], None]:
        """Sonsuz sentetik gürültü üretir."""
        current_time = datetime.now(UTC)
        while True:
            snapshot = []
            for i in range(1, 5):  # 4 bearing
                machine_id = f"bearing_{i}"
                axis: Literal["x", "y"] = "x"
                # 20480 noktalık rastgele beyaz gürültü (-1.0 ile 1.0 arası)
                samples = [random.uniform(-1.0, 1.0) for _ in range(20480)]
                snapshot.append((machine_id, axis, samples, current_time))

            yield snapshot
            current_time += timedelta(minutes=10)  # NASA IMS 10 dakikada bir ölçüm alır

    async def _read_from_disk(
        self,
    ) -> AsyncGenerator[list[tuple[str, Literal["x", "y"], list[float], datetime]], None]:
        """Gerçek dosyaları tarih sırasına göre okur."""
        files = sorted(os.listdir(self.dataset_path))
        for filename in files:
            filepath = os.path.join(self.dataset_path, filename)
            if not os.path.isfile(filepath):
                continue

            # Dosya adı formatı genelde: 2003.10.22.12.06.24 (Y.m.d.H.M.S)
            try:
                source_timestamp = datetime.strptime(filename, "%Y.%m.%d.%H.%M.%S")
            except ValueError:
                source_timestamp = datetime.now(UTC)

            # Basit bir parser (4 sütunlu sekmeyle ayrılmış float değerleri varsayar)
            b1, b2, b3, b4 = [], [], [], []
            with open(filepath) as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        try:
                            b1.append(float(parts[0]))
                            b2.append(float(parts[1]))
                            b3.append(float(parts[2]))
                            b4.append(float(parts[3]))
                        except ValueError:
                            pass

            snapshot: list[tuple[str, Literal["x", "y"], list[float], datetime]] = [
                ("bearing_1", "x", b1, source_timestamp),
                ("bearing_2", "x", b2, source_timestamp),
                ("bearing_3", "x", b3, source_timestamp),
                ("bearing_4", "x", b4, source_timestamp),
            ]
            yield snapshot
