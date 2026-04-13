from datetime import datetime, timezone
from typing import List
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings

ALMATY_TZ = ZoneInfo("Asia/Almaty")


def fmt_dt(dt: datetime) -> str:
    """Format a naive UTC datetime for display in Asia/Almaty timezone."""
    return dt.replace(tzinfo=timezone.utc).astimezone(ALMATY_TZ).strftime("%d.%m.%Y %H:%M")


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str
    KASPI_ACCESS_FEE_LINK: str = "https://kaspi.kz/pay"
    KASPI_WINNER_LINK: str = "https://kaspi.kz/pay"
    SUPERADMIN_IDS: str = ""

    @property
    def superadmin_ids(self) -> List[int]:
        if not self.SUPERADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.SUPERADMIN_IDS.split(",") if x.strip()]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
