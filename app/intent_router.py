from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.parsers import FOOD_KEYWORDS, contains_food, looks_like_evening_summary, looks_like_morning

TRAINING_WORDS = ("push", "pull", "leg", "胸", "背", "腿", "肩", "卧推", "深蹲", "高位下拉", "划船", "哑铃", "杠铃")
RECOVERY_WORDS = ("酸痛", "doms", "疲劳", "困", "恢复", "没精神", "肩膀酸", "背酸", "腿酸")
SOCIAL_WORDS = ("客户", "应酬", "聚餐", "喝酒", "啤酒", "威士忌", "烧鸟", "居酒屋", "ktv")
QUERY_WORDS = ("日志", "本周", "本月", "统计", "日报", "训练记录", "体重趋势", "最近7天", "近7天", "最近30天", "近30天", "近90天", "最近90天")


@dataclass(slots=True)
class RoutedMessage:
    day: date
    intents: set[str] = field(default_factory=set)
    query: str = ""
    water_liters: float | None = None


def target_day(text: str, today: date) -> date:
    if "前天" in text:
        return today - timedelta(days=2)
    if "昨天" in text:
        return today - timedelta(days=1)
    return today


def _chinese_number(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        digits = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
        if value in digits:
            return float(digits[value])
        if value == "半":
            return 0.5
    return None


def extract_water_liters(text: str) -> float | None:
    patterns = (
        r"(\d+(?:\.\d+)?|[零一二两三四五六七八九半])\s*(?:l|升|公升)(?:水)?",
        r"(\d+(?:\.\d+)?)\s*(?:ml|毫升)",
    )
    for index, pattern in enumerate(patterns):
        match = re.search(pattern, text, re.I)
        if match:
            number = _chinese_number(match.group(1))
            return round(number / 1000, 3) if number is not None and index == 1 else number
    return None


def route_message(text: str, today: date) -> RoutedMessage:
    clean = text.strip()
    low = clean.lower()
    result = RoutedMessage(day=target_day(clean, today))
    if clean in {"今天", "昨天", "本周", "本月", "最近7天", "近7天", "最近30天", "近30天", "近90天", "最近90天"} or any(word in low for word in QUERY_WORDS):
        result.intents.add("query")
        result.query = clean
        return result
    if looks_like_morning(clean) or any(word in clean for word in ("体重", "睡眠", "排便", "精神")):
        result.intents.add("morning")
    if looks_like_evening_summary(clean):
        result.intents.add("evening")
    water = extract_water_liters(clean)
    if water is not None and any(word in low for word in ("水", "喝", "饮水", "目前", "已经", "今天")):
        result.intents.add("water")
        result.water_liters = water
    if contains_food(clean) or "没吃" in clean:
        result.intents.add("diet")
    if "开始训练" in clean:
        result.intents.add("training_start")
    elif "训练完成" in clean:
        result.intents.add("training_complete")
    elif any(word in low for word in TRAINING_WORDS) or any(word in clean for word in ("没训练", "不训练", "未训练")):
        result.intents.add("training")
    if any(word in low for word in RECOVERY_WORDS):
        result.intents.add("recovery")
    if any(word in low for word in SOCIAL_WORDS):
        result.intents.add("social")
    if "准备睡觉" in clean:
        result.intents.add("bedtime")
    if not result.intents:
        result.intents.add("note")
    return result
