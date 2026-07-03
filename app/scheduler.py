from __future__ import annotations

import logging
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.coach import CoachService
from app.config import Settings
from app.line_client import LineClient
from app.messages import EVENING_PROMPT, MORNING_PROMPT
from app.reports import create_weekly_charts, daily_report, weekly_report
from app.storage import Storage

logger = logging.getLogger(__name__)


class CoachScheduler:
    def __init__(self, storage: Storage, line: LineClient, coach: CoachService, settings: Settings):
        self.storage, self.line, self.coach, self.settings = storage, line, coach, settings
        self.scheduler = AsyncIOScheduler(timezone=settings.timezone)

    @staticmethod
    def _parts(value: str) -> tuple[int, int]:
        hour, minute = value.split(":")
        return int(hour), int(minute)

    def start(self) -> None:
        mh, mm = self._parts(self.settings.morning_reminder_time)
        eh, em = self._parts(self.settings.evening_reminder_time)
        wh, wm = self._parts(self.settings.weekly_report_time)
        self.scheduler.add_job(
            self.morning, CronTrigger(hour=mh, minute=mm), id="morning", replace_existing=True
        )
        self.scheduler.add_job(
            self.evening, CronTrigger(hour=eh, minute=em), id="evening", replace_existing=True
        )
        self.scheduler.add_job(
            self.weekly,
            CronTrigger(day_of_week="sun", hour=wh, minute=wm),
            id="weekly",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("Scheduler started in timezone %s", self.settings.timezone)

    def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def morning(self) -> None:
        for user in self.storage.list_users():
            self.storage.set_phase(user, "morning")
            self.line.push_text(user, MORNING_PROMPT)

    def evening(self) -> None:
        for user in self.storage.list_users():
            self.storage.set_phase(user, "evening")
            self.line.push_text(user, EVENING_PROMPT)

    def daily_reports(self) -> None:
        for user in self.storage.list_users():
            record = self.storage.get_record(user, self.coach.today())
            if record:
                self.line.push_text(
                    user,
                    "《ChatGPT日报》\n" + daily_report(record, self.storage.list_records(user)),
                )

    def weekly(self) -> None:
        for user in self.storage.list_users():
            records = self.storage.list_records(user)
            self.line.push_text(user, weekly_report(records, self.coach.today()))
            for path in create_weekly_charts(records, Path("reports"), user):
                url = f"{self.settings.base_url.rstrip('/')}/reports/{path.name}"
                self.line.push_image(user, url)
