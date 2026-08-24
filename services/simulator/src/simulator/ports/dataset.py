from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Literal, Protocol


class DatasetProvider(Protocol):
    """
    Veri kaynağını soyutlayan arayüz.
    İster NASA IMS dosyalarından okusun, ister sentetik gürültü üretsin.
    """

    def stream_snapshots(
        self,
    ) -> AsyncGenerator[list[tuple[str, Literal["x", "y"], list[float], datetime]], None]:
        """
        Sürekli olarak bir sonraki anlık veriyi (snapshot) döndürür.
        Bir snapshot, tüm sensörlerin (örn. 4 rulman x veya y ekseni) eşzamanlı ölçümlerini içerir.

        Yields:
            List of tuples: (machine_id, axis, samples, source_timestamp)
            Örn: [("bearing_1", "x", [0.01, -0.02, ...], datetime(...)), ...]
        """
        ...
