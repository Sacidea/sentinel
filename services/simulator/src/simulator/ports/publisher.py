from typing import Protocol


class MessagePublisher(Protocol):
    """
    Kafka veya herhangi bir mesaj kuyruğuna mesaj gönderme arayüzü.
    """

    async def publish(self, topic: str, key: str, message: bytes) -> None:
        """
        Mesajı asenkron olarak kuyruğa yazar.
        
        Args:
            topic: Hedef topic adı (örn. sensor.vibration.raw)
            key: Partitioning için kullanılacak anahtar (örn. machine_id)
            message: Gönderilecek ham veri (JSON bytes)
        """
        ...

    async def start(self) -> None:
        """Bağlantıyı başlatır."""
        ...

    async def stop(self) -> None:
        """Bağlantıyı kapatır."""
        ...
