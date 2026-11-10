from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    wa_access_token: str = ""
    wa_phone_number_id: str = ""
    wa_app_secret: str = ""
    wa_verify_token: str = ""
    wa_api_version: str = "v21.0"
    business_timezone: str = "Asia/Riyadh"
    business_working_days: str = "sun,mon,tue,wed,thu"
    booking_days_ahead: int = Field(7, ge=1, le=10)  # WhatsApp lists hold at most 10 rows

    @field_validator("business_timezone")
    @classmethod
    def _check_tz(cls, v: str) -> str:
        ZoneInfo(v)  # raises if unknown
        return v

    @field_validator("business_working_days")
    @classmethod
    def _check_days(cls, v: str) -> str:
        days = [d.strip().lower() for d in v.split(",") if d.strip()]
        if not days or any(d not in WEEKDAYS for d in days):
            raise ValueError(f"must be a comma-separated subset of {','.join(WEEKDAYS)}")
        return ",".join(days)

    @property
    def working_days(self) -> frozenset[int]:
        """Working days as Python weekday numbers (Monday = 0)."""
        return frozenset(WEEKDAYS.index(d) for d in self.business_working_days.split(","))


@lru_cache
def get_settings() -> Settings:
    return Settings()
