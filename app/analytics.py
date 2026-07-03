from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import mean

from app.models import DailyRecord


def avg(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return round(mean(present), 2) if present else None


@dataclass(slots=True)
class Summary:
    average_weight_7d: float | None
    average_weight_30d: float | None
    total_weight_loss: float | None
    kg_to_goal: float | None
    streak: int
    average_sleep: float | None
    average_water: float | None
    training_count: int
    average_protein: float | None


def calculate_summary(records: list[DailyRecord], goal: float = 85.0) -> Summary:
    ordered = sorted(records, key=lambda r: r.record_date)
    weights = [r for r in ordered if r.weight is not None]
    latest_weight = weights[-1].weight if weights else None
    total_loss = (
        round(weights[0].weight - latest_weight, 2) if len(weights) >= 2 else 0 if weights else None
    )
    return Summary(
        average_weight_7d=avg([r.weight for r in ordered[-7:]]),
        average_weight_30d=avg([r.weight for r in ordered[-30:]]),
        total_weight_loss=total_loss,
        kg_to_goal=round(max(0, latest_weight - goal), 2) if latest_weight is not None else None,
        streak=calculate_streak(ordered),
        average_sleep=avg([r.sleep for r in ordered[-7:]]),
        average_water=avg([r.water for r in ordered[-7:]]),
        training_count=sum(is_training(r) for r in ordered[-7:]),
        average_protein=avg([r.protein for r in ordered[-7:]]),
    )


def calculate_streak(records: list[DailyRecord], today: date | None = None) -> int:
    if not records:
        return 0
    dates = {r.record_date for r in records}
    cursor = today or max(dates)
    if cursor not in dates:
        cursor = max(dates)
    count = 0
    while cursor in dates:
        count += 1
        cursor -= timedelta(days=1)
    return count


def is_training(record: DailyRecord) -> bool:
    return bool(record.trained and record.trained not in {"否", "无", "休息", "未训练", "没有训练"})


def alerts(records: list[DailyRecord], protein_target: float = 120) -> list[str]:
    ordered = sorted(records, key=lambda r: r.record_date)
    result: list[str] = []
    if len(ordered) >= 2 and all(r.sleep is not None and r.sleep < 6.5 for r in ordered[-2:]):
        result.append("建议今晚早点休息。")
    if ordered and ordered[-1].water is not None and ordered[-1].water < 2:
        result.append("今天饮水不足。")
    if len(ordered) >= 2 and all(not is_training(r) for r in ordered[-2:]):
        result.append("建议安排训练。")
    if ordered and ordered[-1].protein is not None and ordered[-1].protein < protein_target:
        result.append("建议补充蛋白质。")
    recent_weights = [r.weight for r in ordered[-7:] if r.weight is not None]
    if len(recent_weights) >= 7 and min(recent_weights[1:]) >= recent_weights[0]:
        result.append("连续7天体重没有下降，建议调整饮食。")
    return result


def coaching_analysis(record: DailyRecord, records: list[DailyRecord]) -> list[str]:
    notes: list[str] = []
    if record.sleep is not None:
        notes.append("睡眠略少。" if record.sleep < 6.5 else "睡眠达到基础恢复要求。")
    if record.energy is not None and record.energy <= 5:
        notes.append("今天恢复一般。")
    if record.protein is not None:
        notes.append("蛋白质充足。" if record.protein >= 120 else "蛋白质偏低。")
    if record.water is not None:
        notes.append("饮水达标。" if record.water >= 3 else "饮水还可增加。")
    notes.extend(alerts(records))
    if record.soreness and any(
        int(x) >= 4 for x in __import__("re").findall(r"\d+", record.soreness)
    ):
        notes.append("酸痛较明显，明天避免重复高强度刺激该部位。")
    return list(dict.fromkeys(notes))
