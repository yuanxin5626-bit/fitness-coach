from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.analytics import calculate_summary
from app.config import Settings
from app.messages import EVENING_PROMPT, HELP, MORNING_PROMPT, WELCOME
from app.models import DailyRecord
from app.parsers import (
    ParseError,
    contains_food,
    estimate_protein,
    looks_like_evening_summary,
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

        # Explicit events always override the current conversational phase.
        if "训练完成" in clean:
            self.storage.set_phase(user_id, "training_summary")
            return (
                "训练完成，辛苦了 ✅\n\n"
                "请发送训练总结（可以一次发送，也可以稍后补录）：\n"
                "训练内容、饮水、饮食、酸痛、整体状态。"
            )
        if "开始训练" in clean:
            record = self._record(user_id)
            record.trained = "是"
            self._touch(record)
            self.storage.upsert_record(record)
            self.storage.set_phase(user_id, "training")
            return "已开始记录本次训练 💪\n直接发送动作、重量、次数即可；结束时回复“训练完成”。"
        if "准备睡觉" in clean:
            self.storage.set_phase(user_id, "bedtime")
            return "收到，进入睡前总结 🌙\n请发送今天的饮水、饮食、酸痛和整体状态；缺少的项目以后也能补录。"

        phase = self.storage.get_phase(user_id)
        try:
            # Structured payloads are recognized independently from phase.
            if looks_like_morning(clean):
                return self.save_morning(user_id, clean)
            if looks_like_evening_summary(clean):
                return self.save_evening(user_id, clean)
            if contains_food(clean):
                return self.save_diet(user_id, clean)
            if phase == "morning":
                return self.save_morning(user_id, clean)
            if phase in {"evening", "training_summary", "bedtime"}:
                return self.save_evening(user_id, clean)
            if phase == "training":
                return self.save_training_detail(user_id, clean)
        except ParseError as exc:
            return f"输入还差一点：{exc}\n\n请修正后重新发送，或回复“帮助”查看命令。"
        return (
            WELCOME
            if is_new
            else "我还不确定你想记录什么。你可以直接发送饮食、晨间四行数据，或回复“开始训练”“训练完成”“准备睡觉”。"
        )

    def _record(self, user_id: str) -> DailyRecord:
        return self.storage.get_record(user_id, self.today()) or DailyRecord(
            self.today(), user_id=user_id
        )

    def _touch(self, record: DailyRecord) -> None:
        record.updated_at = datetime.now(ZoneInfo(self.settings.timezone)).isoformat(
            timespec="seconds"
        )

    def save_diet(self, user_id: str, text: str) -> str:
        record = self._record(user_id)
        record.diet = "\n".join(part for part in (record.diet.strip(), text.strip()) if part)
        record.protein = estimate_protein(record.diet)
        self._touch(record)
        self.storage.upsert_record(record)
        return f"饮食已记录 ✅\n当前蛋白质估算：{record.protein}g\n晨间数据未填写也不影响继续记录。"

    def save_training_detail(self, user_id: str, text: str) -> str:
        record = self._record(user_id)
        record.trained = record.trained or "是"
        record.training_details = "\n".join(
            part for part in (record.training_details.strip(), text.strip()) if part
        )
        self._touch(record)
        self.storage.upsert_record(record)
        return "训练内容已追加 ✅\n可继续发送动作，结束时回复“训练完成”。"

    def save_morning(self, user_id: str, text: str) -> str:
        data = parse_morning(text)
        record = self._record(user_id)
        record.weight, record.sleep = data.weight, data.sleep
        record.bowel_movement, record.energy = data.bowel_movement, data.energy
        self._touch(record)
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
        self._touch(record)
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
