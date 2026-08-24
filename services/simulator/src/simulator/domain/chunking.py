import uuid
from datetime import datetime,timezone
from typing import Literal

from contracts.events import RawVibrationWindow


def create_chunks(
    machine_id: str,
    axis: Literal["x", "y"],
    samples: list[float],
    source_timestamp: datetime,
    total_chunks: int = 8,
) -> list[RawVibrationWindow]:
    """
    Ham sinyali (örn. 20.480 örnek) alıp belirtilen sayıda (varsayılan 8) chunk'a böler.
    Tüm chunk'lar aynı snapshot_id'yi paylaşır.

    Args:
        machine_id: Rulman veya makine kimliği (örn. bearing_1)
        axis: İlgili eksen (x veya y)
        samples: Ham sinyal dizisi
        source_timestamp: Orijinal dosyanın temsil ettiği zaman damgası
        total_chunks: Sinyalin bölüneceği parça sayısı

    Returns:
        List[RawVibrationWindow]: Kafka'ya gönderilmeye hazır chunk objeleri
    """
    if not samples:
        return []

    snapshot_id = uuid.uuid4()
    occurred_at = datetime.now(timezone.utc)  # Canlı stream zamanı
    
    chunk_size = len(samples) // total_chunks
    # Eğer tam bölünmüyorsa son chunk biraz daha uzun olabilir.
    
    chunks = []
    for i in range(total_chunks):
        start_idx = i * chunk_size
        # Son chunk geri kalan tüm sample'ları alır
        end_idx = start_idx + chunk_size if i < total_chunks - 1 else len(samples)
        
        chunk_samples = samples[start_idx:end_idx]
        
        window = RawVibrationWindow(
            snapshot_id=snapshot_id,
            chunk_index=i,
            total_chunks=total_chunks,
            machine_id=machine_id,
            axis=axis,
            samples=chunk_samples,
            occurred_at=occurred_at,
            source_timestamp=source_timestamp
        )
        chunks.append(window)

    return chunks
