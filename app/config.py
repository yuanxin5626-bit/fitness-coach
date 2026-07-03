from __future__ import annotations

from datetime import date
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    timezone: str = "Asia/Tokyo"
    base_url: str = "http://localhost:8000"
    port: int = 8000
    line_channel_secret: str = ""
    line_channel_access_token: str = ""
    default_line_user_id: str = ""
    google_sheet_id: str = ""
    google_service_account_file: str = "service-account.json"
    google_service_account_json: str = ""
    google_apps_script_url: str = ""
    google_apps_script_secret: str = ""
    enable_scheduler: bool = True
    cron_secret: str = ""
    morning_reminder_time: str = "07:30"
    evening_reminder_time: str = "22:00"
    weekly_report_time: str = "22:30"
    weight_goal_kg: float = 85.0
    target_date: date = date(2026, 9, 1)
    protein_target_g: float = 130.0
    water_target_l: float = 3.0
    profile_name: str = "Fitness Coach User"
    height_cm: int = 177
    initial_weight_kg: float = 91.0
    scheduler_lock_file: str = Field(default="/tmp/fitness-coach-scheduler.lock")


@lru_cache
def get_settings() -> Settings:
    return Settings()
