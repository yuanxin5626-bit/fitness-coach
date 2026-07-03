from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.analytics import calculate_summary
from app.config import Settings
from app.messages import EVENING_PROMPT, HELP, MORNING_PROMPT, WELCOME
from app.models import DailyRecord
from app.parsers import (
    ParseError,
    estimate_protein,
    looks_like_morning,
    parse_evening,
    parse_morning,
)
from app.reports import daily_report, weekly_report
from app.storage import Storage


class CoachService:
    def __init__(self, storage: Storage, settings: Settings):
        self.storage = storage
        self.settings = settings

    def today(self):
        return datetime.now(ZoneInfo(self.settings.timezone)).date()

    def handle_text(self, user_id: str, text: str) -> str:
        is_new = user_id not in self.storage.list_users()
        self.storage.register_user(user_id)
        clean = text.strip()
        command = clean.lower()
        if command in {"帮助", "help", "菜单"}:
            return HELP
        if command in {"晨间", "早安", "morning"}:
            self.storage.set_phase(user_id, "morning")
            return MORNING_PROMPT
        if command in {"晚间", "晚上", "evening"}:
            self.storage.set_phase(user_id, "evening")
            return EVENING_PROMPT
        if command in {"日报", "daily"}:
            return self.make_daily(user_id)
        if command in {"周报", "weekly"}:
            return weekly_report(self.storage.list_records(user_id), self.today())
        if command in {"统计", "stats", "状态"}:
            return self.stats(user_id)

        phase = self.storage.get_phase(user_id)
        try:
            if phase == "morning" or looks_like_morning(clean):
                return self.save_morning(user_id, clean)
            if phase == "evening":
                return self.save_evening(user_id, clean)
        except ParseError as exc:
            return f"输入还差一点：{exc}\n\n请修正后重新发送，或回复“帮助”查看命令。"
        return (
            WELCOME
            if is_new
            else "我还不确定这是晨间还是晚间数据。请先回复“晨间”或“晚间”，我会引导你填写。"
        )

    def _record(self, user_id: str) -> DailyRecord:
        return self.storage.get_record(user_id, self.today()) or DailyRecord(
            self.today(), user_id=user_id
        )

    def save_morning(self, user_id: str, text: str) -> str:
        data = parse_morning(text)
        record = self._record(user_id)
        record.weight, record.sleep = data.weight, data.sleep
        record.bowel_movement, record.energy = data.bowel_movement, data.energy
        record.updated_at = datetime.now(ZoneInfo(self.settings.timezone)).isoformat(
            timespec="seconds"
        )
        self.storage.upsert_record(record)
        self.storage.set_phase(user_id, "")
        return f"晨间数据已保存 ✅\n体重 {data.weight}kg｜睡眠 {data.sleep}h｜精神 {data.energy}/10"

    def save_evening(self, user_id: str, text: str) -> str:
        data = parse_evening(text)
        record = self._record(user_id)
        record.trained, record.training_details = data.trained, data.training_details
        record.water, record.diet, record.soreness = data.water, data.diet, data.soreness
        record.overall_score, record.notes = data.overall_score, data.notes
        record.protein = estimate_protein(data.diet)
        record.updated_at = datetime.now(ZoneInfo(self.settings.timezone)).isoformat(
            timespec="seconds"
        )
        self.storage.upsert_record(record)
        self.storage.set_phase(user_id, "")
        history = self.storage.list_records(user_id)
        header = f"晚间数据已保存 ✅\n蛋白质估算：{record.protein}g\n\n《ChatGPT日报》\n"
        return header + daily_report(record, history)

    def make_daily(self, user_id: str) -> str:
        record = self.storage.get_record(user_id, self.today())
        return (
            daily_report(record, self.storage.list_records(user_id))
            if record
            else "今天还没有记录。回复“晨间”或“晚间”开始填写。"
        )

    def stats(self, user_id: str) -> str:
        summary = calculate_summary(
            self.storage.list_records(user_id), self.settings.weight_goal_kg
        )

        def show(value, suffix=""):
            return f"{value}{suffix}" if value is not None else "暂无"

        return f"""📈 当前统计
7日平均体重：{show(summary.average_weight_7d, "kg")}
30日平均体重：{show(summary.average_weight_30d, "kg")}
累计下降：{show(summary.total_weight_loss, "kg")}
距离目标：{show(summary.kg_to_goal, "kg")}
连续打卡：{summary.streak}天
平均睡眠（7日）：{show(summary.average_sleep, "h")}
平均饮水（7日）：{show(summary.average_water, "L")}
训练次数（7日）：{summary.training_count}次
蛋白质平均值（7日）：{show(summary.average_protein, "g")}"""
