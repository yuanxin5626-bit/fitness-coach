from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import date, datetime
from pathlib import Path

import gspread
import httpx
from google.oauth2.service_account import Credentials

from app.config import Settings
from app.models import SHEET_HEADERS, USER_HEADERS, DailyRecord

logger = logging.getLogger(__name__)


class Storage(ABC):
    @abstractmethod
    def upsert_record(self, record: DailyRecord) -> None: ...

    @abstractmethod
    def get_record(self, user_id: str, day: date) -> DailyRecord | None: ...

    @abstractmethod
    def list_records(self, user_id: str, limit: int | None = None) -> list[DailyRecord]: ...

    @abstractmethod
    def register_user(self, user_id: str) -> None: ...

    @abstractmethod
    def list_users(self) -> list[str]: ...

    @abstractmethod
    def set_phase(self, user_id: str, phase: str) -> None: ...

    @abstractmethod
    def get_phase(self, user_id: str) -> str: ...


class GoogleSheetsStorage(Storage):
    def __init__(self, settings: Settings):
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        if settings.google_service_account_json:
            info = json.loads(settings.google_service_account_json)
            credentials = Credentials.from_service_account_info(info, scopes=scopes)
        else:
            path = Path(settings.google_service_account_file)
            credentials = Credentials.from_service_account_file(path, scopes=scopes)
        client = gspread.authorize(credentials)
        self.spreadsheet = client.open_by_key(settings.google_sheet_id)
        self.records = self._worksheet("每日记录", SHEET_HEADERS)
        self.users = self._worksheet("用户", USER_HEADERS)

    def _worksheet(self, title: str, headers: list[str]):
        try:
            ws = self.spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title, rows=1000, cols=len(headers))
        if not ws.row_values(1):
            ws.append_row(headers)
            ws.format(
                "1:1",
                {
                    "textFormat": {"bold": True},
                    "backgroundColor": {"red": 0.85, "green": 0.92, "blue": 1},
                },
            )
            ws.freeze(rows=1)
        return ws

    def upsert_record(self, record: DailyRecord) -> None:
        key = record.record_date.isoformat()
        rows = self.records.get_all_records()
        for index, row in enumerate(rows, start=2):
            if str(row.get("日期")) == key and str(row.get("用户ID")) == record.user_id:
                self.records.update(values=[record.to_sheet_row()], range_name=f"A{index}:O{index}")
                return
        self.records.append_row(record.to_sheet_row(), value_input_option="USER_ENTERED")

    def get_record(self, user_id: str, day: date) -> DailyRecord | None:
        target = day.isoformat()
        for row in self.records.get_all_records():
            if str(row.get("日期")) == target and str(row.get("用户ID")) == user_id:
                return DailyRecord.from_sheet_row({k: str(v) for k, v in row.items()})
        return None

    def list_records(self, user_id: str, limit: int | None = None) -> list[DailyRecord]:
        result = [
            DailyRecord.from_sheet_row({k: str(v) for k, v in row.items()})
            for row in self.records.get_all_records()
            if str(row.get("用户ID")) == user_id and row.get("日期")
        ]
        result.sort(key=lambda item: item.record_date)
        return result[-limit:] if limit else result

    def register_user(self, user_id: str) -> None:
        if user_id not in self.list_users():
            self.users.append_row([user_id, "", datetime.now().isoformat(timespec="seconds"), "是"])

    def list_users(self) -> list[str]:
        return [
            str(row["用户ID"])
            for row in self.users.get_all_records()
            if row.get("用户ID") and str(row.get("启用提醒", "是")) != "否"
        ]

    def set_phase(self, user_id: str, phase: str) -> None:
        self.register_user(user_id)
        for index, row in enumerate(self.users.get_all_records(), start=2):
            if str(row.get("用户ID")) == user_id:
                self.users.update(
                    values=[[phase, datetime.now().isoformat(timespec="seconds")]],
                    range_name=f"B{index}:C{index}",
                )
                return

    def get_phase(self, user_id: str) -> str:
        for row in self.users.get_all_records():
            if str(row.get("用户ID")) == user_id:
                return str(row.get("收集阶段", ""))
        return ""


class AppsScriptStorage(Storage):
    """Google Sheets through a free Apps Script Web App, without Cloud Billing."""

    def __init__(self, url: str, secret: str):
        self.url = url
        self.secret = secret

    def _get(self, action: str, **params):
        response = httpx.get(
            self.url,
            params={"action": action, "secret": self.secret, **params},
            timeout=30,
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(payload.get("error", "Apps Script request failed"))
        return payload.get("data")

    def _post(self, action: str, **data):
        response = httpx.post(
            self.url,
            json={"action": action, "secret": self.secret, **data},
            timeout=30,
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(payload.get("error", "Apps Script request failed"))
        return payload.get("data")

    def upsert_record(self, record: DailyRecord) -> None:
        self._post("upsert_record", row=record.to_sheet_row())

    def get_record(self, user_id: str, day: date) -> DailyRecord | None:
        row = self._get("get_record", user_id=user_id, day=day.isoformat())
        return DailyRecord.from_sheet_row(row) if row else None

    def list_records(self, user_id: str, limit: int | None = None) -> list[DailyRecord]:
        rows = self._get("list_records", user_id=user_id, limit=limit or "") or []
        return [DailyRecord.from_sheet_row(row) for row in rows]

    def register_user(self, user_id: str) -> None:
        self._post("register_user", user_id=user_id)

    def list_users(self) -> list[str]:
        return self._get("list_users") or []

    def set_phase(self, user_id: str, phase: str) -> None:
        self._post("set_phase", user_id=user_id, phase=phase)

    def get_phase(self, user_id: str) -> str:
        return self._get("get_phase", user_id=user_id) or ""


class MemoryStorage(Storage):
    """Development/test fallback. Production deliberately requires Google Sheets."""

    def __init__(self):
        self.data: dict[tuple[str, date], DailyRecord] = {}
        self.users: dict[str, str] = {}

    def upsert_record(self, record: DailyRecord) -> None:
        self.data[(record.user_id, record.record_date)] = record

    def get_record(self, user_id: str, day: date) -> DailyRecord | None:
        return self.data.get((user_id, day))

    def list_records(self, user_id: str, limit: int | None = None) -> list[DailyRecord]:
        values = sorted(
            (r for (uid, _), r in self.data.items() if uid == user_id), key=lambda r: r.record_date
        )
        return values[-limit:] if limit else values

    def register_user(self, user_id: str) -> None:
        self.users.setdefault(user_id, "")

    def list_users(self) -> list[str]:
        return list(self.users)

    def set_phase(self, user_id: str, phase: str) -> None:
        self.users[user_id] = phase

    def get_phase(self, user_id: str) -> str:
        return self.users.get(user_id, "")


def build_storage(settings: Settings) -> Storage:
    if settings.google_apps_script_url:
        return AppsScriptStorage(
            settings.google_apps_script_url, settings.google_apps_script_secret
        )
    if settings.google_sheet_id:
        return GoogleSheetsStorage(settings)
    if settings.app_env == "production":
        raise RuntimeError(
            "Production requires GOOGLE_APPS_SCRIPT_URL or Google Sheets service-account settings"
        )
    logger.warning("Google Sheets is not configured; using non-persistent in-memory storage")
    return MemoryStorage()
