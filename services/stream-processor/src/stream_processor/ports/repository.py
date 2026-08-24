from typing import Protocol

from contracts.events import RawVibrationWindow


class RawWindowRepository(Protocol):
    """Walking Skeleton sırasında ham chunk izini saklar."""

    async def save(self, window: RawVibrationWindow) -> None:
        """Bir doğrulanmış ham pencereyi kalıcı hâle getirir."""
