from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.analytics import calculate_summary
from app.config import Settings
from app.intent_router import route_message
from app.messages import EVENING_PROMPT, HELP, MORNING_PROMPT
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
        self.storage.register_user(user_id)
        clean = text.strip()
        command = clean.lower()
        routed = route_message(clean, self.today())
        if "query" in routed.intents:
            return self.query(user_id, routed.query)
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
            if phase == "training" and routed.intents == {"note"}:
                routed.intents = {"training"}
            record = self.storage.get_record(user_id, routed.day) or DailyRecord(
                routed.day, user_id=user_id
            )
            self._append(record, "messages", f"{datetime.now(ZoneInfo(self.settings.timezone)).strftime('%H:%M')} {clean}")
            feedback: list[str] = []
            evening_applied = False
            if "evening" in routed.intents:
                data = parse_evening(clean)
                record.trained, record.training_details = data.trained, data.training_details
                record.water, record.diet, record.soreness = data.water, data.diet, data.soreness
                record.overall_score, record.notes = data.overall_score, data.notes
                record.protein = estimate_protein(record.diet)
                evening_applied = True
                feedback.append("晚间总结")
            if "morning" in routed.intents:
                self._apply_morning(record, clean)
                feedback.append("晨间数据")
            if "water" in routed.intents and not evening_applied:
                record.water = routed.water_liters
                feedback.append(f"饮水 {record.water}L")
            if "diet" in routed.intents and not evening_applied:
                diet_text = self._normalize_diet(clean)
                self._append(record, "diet", diet_text)
                record.protein = estimate_protein(record.diet)
                feedback.append("饮食")
            if "training_start" in routed.intents:
                record.trained = "是"
                self.storage.set_phase(user_id, "training")
                feedback.append("开始训练")
            if "training_complete" in routed.intents:
                record.trained = record.trained or "是"
                self.storage.set_phase(user_id, "training_summary")
                feedback.append("训练完成")
            if "training" in routed.intents and not evening_applied:
                if any(word in clean for word in ("没训练", "不训练", "未训练")):
                    record.trained = "否"
                else:
                    record.trained = record.trained or "是"
                    self._append(record, "training_details", clean)
                feedback.append("训练")
            if "recovery" in routed.intents:
                self._append(record, "recovery", clean)
                self._append(record, "soreness", clean)
                feedback.append("恢复")
            if "social" in routed.intents:
                self._append(record, "social", clean)
                self._append(record, "notes", clean)
                feedback.append("应酬")
            if "bedtime" in routed.intents:
                self.storage.set_phase(user_id, "bedtime")
                feedback.append("睡前总结")
            if "note" in routed.intents:
                self._append(record, "notes", clean)
                feedback.append("备注")
            self._touch(record)
            self.storage.upsert_record(record)
            date_label = "昨天" if routed.day == self.today() - timedelta(days=1) else routed.day.isoformat()
            result = f"已记录到{date_label}：{'、'.join(dict.fromkeys(feedback))} ✅"
            if evening_applied:
                result = "晚间数据已保存 ✅\n\n《ChatGPT日报》\n" + daily_report(
                    record, self.storage.list_records(user_id)
                )
            elif routed.intents == {"morning"}:
                result = f"晨间数据已保存 ✅（{date_label}）"
            elif routed.intents == {"diet"}:
                result = f"饮食已记录 ✅（{date_label}）\n当前蛋白质估算：{record.protein}g"
            elif "training_start" in routed.intents:
                result = f"已开始记录训练 💪（{date_label}）\n继续发送动作、重量和次数；结束时说“训练完成”。"
            elif "training_complete" in routed.intents:
                result += "\n可继续补充饮水、饮食、酸痛和整体状态。"
            elif phase == "training" and "training" in routed.intents:
                result = f"训练内容已追加 ✅（{date_label}）"
            elif "bedtime" in routed.intents:
                result += "\n今天缺少的数据可以现在补，也可以明天再补。"
            return result
        except ParseError as exc:
            return self._uncertain(str(exc))

    def _record(self, user_id: str) -> DailyRecord:
        return self.storage.get_record(user_id, self.today()) or DailyRecord(
            self.today(), user_id=user_id
        )

    def _touch(self, record: DailyRecord) -> None:
        record.updated_at = datetime.now(ZoneInfo(self.settings.timezone)).isoformat(
            timespec="seconds"
        )

    @staticmethod
    def _append(record: DailyRecord, field: str, value: str) -> None:
        current = getattr(record, field).strip()
        if value.strip() and value.strip() not in current.splitlines():
            setattr(record, field, "\n".join(part for part in (current, value.strip()) if part))

    @staticmethod
    def _normalize_diet(text: str) -> str:
        aliases = {"早餐": ("早餐", "早饭"), "午餐": ("午餐", "午饭"), "晚餐": ("晚餐", "晚饭")}
        for meal, words in aliases.items():
            if any(f"没吃{word}" in text or f"没有吃{word}" in text for word in words):
                return f"{meal}：未进食"
        return text

    def _apply_morning(self, record: DailyRecord, text: str) -> None:
        if looks_like_morning(text):
            data = parse_morning(text)
            record.weight, record.sleep = data.weight, data.sleep
            record.bowel_movement, record.energy = data.bowel_movement, data.energy
            return
        patterns = {
            "weight": r"体重\s*[：:]?\s*(\d+(?:\.\d+)?)",
            "sleep": r"睡眠\s*[：:]?\s*(\d+(?:\.\d+)?)",
            "energy": r"精神\s*[：:]?\s*(\d{1,2})",
        }
        for field, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                setattr(record, field, int(match.group(1)) if field == "energy" else float(match.group(1)))
        if "排便" in text:
            record.bowel_movement = "否" if any(x in text for x in ("没", "未", "否", "无")) else "是"

    @staticmethod
    def _uncertain(detail: str = "") -> str:
        return "我没有完全理解。\n猜你想记录：\n① 饮食\n② 饮水\n③ 训练\n④ 恢复\n⑤ 应酬\n⑥ 备注" + (f"\n\n我识别到的问题：{detail}" if detail else "")

    def query(self, user_id: str, text: str) -> str:
        today = self.today()
        if text == "昨天":
            record = self.storage.get_record(user_id, today - timedelta(days=1))
            return daily_report(record, self.storage.list_records(user_id)) if record else "昨天还没有记录。"
        if text in {"本周", "最近7天", "近7天", "周报"}:
            return weekly_report(self.storage.list_records(user_id), today)
        if text in {"本月", "最近30天", "近30天"}:
            return self.range_stats(user_id, 30)
        if text in {"近90天", "最近90天"}:
            return self.range_stats(user_id, 90)
        if text == "统计":
            return self.stats(user_id)
        if "训练记录" in text:
            rows = [r for r in self.storage.list_records(user_id) if r.training_details or r.trained]
            return "\n\n".join(f"{r.record_date}\n{r.trained}\n{r.training_details}" for r in rows[-10:]) or "暂无训练记录。"
        record = self.storage.get_record(user_id, today)
        return daily_report(record, self.storage.list_records(user_id)) if record else "今天还没有记录。"

    def range_stats(self, user_id: str, days: int) -> str:
        cutoff = self.today() - timedelta(days=days - 1)
        records = [r for r in self.storage.list_records(user_id) if r.record_date >= cutoff]
        weights = [r.weight for r in records if r.weight is not None]
        sleep = [r.sleep for r in records if r.sleep is not None]
        water = [r.water for r in records if r.water is not None]
        protein = [r.protein for r in records if r.protein is not None]
        average = lambda values: round(sum(values) / len(values), 1) if values else "暂无"
        decline = round(weights[0] - weights[-1], 1) if len(weights) > 1 else "暂无"
        trained = sum(bool(r.trained and r.trained not in {"否", "休息", "未训练"}) for r in records)
        return (
            f"📈 最近{days}天趋势\n"
            f"体重变化：下降 {decline}kg\n训练次数：{trained}次\n"
            f"平均蛋白：{average(protein)}g\n平均睡眠：{average(sleep)}h\n平均饮水：{average(water)}L"
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
