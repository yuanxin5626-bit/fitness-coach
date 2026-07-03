from __future__ import annotations

import re
from dataclasses import dataclass


class ParseError(ValueError):
    """User-facing validation error."""


@dataclass(slots=True)
class MorningData:
    weight: float
    sleep: float
    bowel_movement: str
    energy: int


@dataclass(slots=True)
class EveningData:
    trained: str
    training_details: str
    water: float
    diet: str
    soreness: str
    overall_score: int
    notes: str = ""


def _nonempty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.replace("\r", "").split("\n") if line.strip()]


def parse_morning(text: str) -> MorningData:
    lines = _nonempty_lines(text)
    if len(lines) < 4:
        raise ParseError("晨间数据需要 4 行：体重、睡眠、排便、精神。")
    try:
        weight = float(re.search(r"\d+(?:\.\d+)?", lines[0]).group())
        sleep = float(re.search(r"\d+(?:\.\d+)?", lines[1]).group())
        energy = int(float(re.search(r"\d+(?:\.\d+)?", lines[3]).group()))
    except (AttributeError, ValueError) as exc:
        raise ParseError("无法识别数字，请按示例输入：90.6 / 6.5 / 是 / 5。") from exc
    if not 35 <= weight <= 250:
        raise ParseError("体重应在 35–250kg 之间，请检查输入。")
    if not 0 <= sleep <= 24:
        raise ParseError("睡眠应在 0–24 小时之间。")
    if not 1 <= energy <= 10:
        raise ParseError("精神状态应为 1–10。")
    bowel = "是" if any(word in lines[2] for word in ("是", "有", "已")) else "否"
    return MorningData(weight, sleep, bowel, energy)


def looks_like_morning(text: str) -> bool:
    lines = _nonempty_lines(text)
    return len(lines) == 4 and bool(re.fullmatch(r"(?:是|否|有|无|已排便|未排便)", lines[2]))


def parse_evening(text: str) -> EveningData:
    lines = _nonempty_lines(text)
    joined = "\n".join(lines)
    water_match = re.search(r"(?:饮水|水)\s*[：:]?\s*(\d+(?:\.\d+)?)\s*[lL升]?", joined)
    score_matches = re.findall(r"(?:整体)?状态\s*[：:]?\s*(\d{1,2})", joined)
    if not water_match:
        raise ParseError("没有识别到饮水量，请写成“饮水 2.8L”。")
    if not score_matches:
        raise ParseError("没有识别到整体状态，请写成“状态：7”。")
    water = float(water_match.group(1))
    score = int(score_matches[-1])
    if not 0 <= water <= 15:
        raise ParseError("饮水量应在 0–15L 之间。")
    if not 1 <= score <= 10:
        raise ParseError("整体状态应为 1–10。")

    first = lines[0]
    trained = "否" if first in {"否", "无", "休息", "未训练", "没有训练"} else first
    diet_start = next(
        (i for i, x in enumerate(lines) if re.match(r"(?:早餐|午餐|晚餐|饮食)[：:]?", x)), None
    )
    soreness_start = next((i for i, x in enumerate(lines) if re.match(r"酸痛[：:]?", x)), None)
    state_start = next(
        (i for i, x in enumerate(lines) if re.match(r"(?:整体)?状态[：:]?", x)), len(lines)
    )
    water_idx = next(i for i, x in enumerate(lines) if water_match.group(0) in x)

    training_end = min(
        i for i in (water_idx, diet_start, soreness_start, state_start) if i is not None
    )
    training_details = "\n".join(lines[1:training_end]).strip()
    if diet_start is not None:
        diet_end = min(i for i in (soreness_start, state_start) if i is not None and i > diet_start)
        diet = "\n".join(lines[diet_start:diet_end])
    else:
        diet = ""
    if soreness_start is not None:
        soreness = "\n".join(lines[soreness_start + 1 : state_start])
    else:
        soreness = ""
    return EveningData(trained, training_details, water, diet, soreness, score)


PROTEIN_RULES: list[tuple[re.Pattern, float, str]] = [
    (re.compile(r"鸡蛋\s*(\d+(?:\.\d+)?)"), 6.5, "count"),
    (re.compile(r"(?:牛奶|豆奶)\s*(\d+(?:\.\d+)?)\s*ml", re.I), 0.033, "amount"),
    (re.compile(r"蛋白粉\s*(\d+(?:\.\d+)?)\s*g", re.I), 0.78, "amount"),
    (re.compile(r"(?:鸡胸|鸡肉)\s*(\d+(?:\.\d+)?)\s*g", re.I), 0.23, "amount"),
    (re.compile(r"(?:牛肉|牛排)\s*(\d+(?:\.\d+)?)\s*g", re.I), 0.22, "amount"),
    (re.compile(r"(?:鲑鱼|三文鱼|鱼肉)\s*(\d+(?:\.\d+)?)\s*g", re.I), 0.21, "amount"),
    (re.compile(r"(?:豆腐)\s*(\d+(?:\.\d+)?)\s*g", re.I), 0.08, "amount"),
]


def estimate_protein(diet: str) -> float:
    """Conservative rule-based estimate; easy to replace with an AI analyzer later."""
    total = 0.0
    for pattern, factor, _ in PROTEIN_RULES:
        total += sum(float(match.group(1)) * factor for match in pattern.finditer(diet))
    meal_defaults = {"牛肉饭": 25, "亲子丼": 25, "便当": 25, "拉面": 18}
    total += sum(value * diet.count(food) for food, value in meal_defaults.items())
    return round(total, 1)
