from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

SHEET_HEADERS = [
    "日期",
    "晨重",
    "睡眠",
    "排便",
    "精神",
    "训练",
    "训练详情",
    "饮水",
    "饮食",
    "蛋白质估算",
    "备注",
    "酸痛",
    "综合评分",
    "用户ID",
    "更新时间",
]
USER_HEADERS = ["用户ID", "收集阶段", "更新时间", "启用提醒"]


@dataclass(slots=True)
class DailyRecord:
    record_date: date
    weight: float | None = None
    sleep: float | None = None
    bowel_movement: str = ""
    energy: int | None = None
    trained: str = ""
    training_details: str = ""
    water: float | None = None
    diet: str = ""
    protein: float | None = None
    notes: str = ""
    soreness: str = ""
    overall_score: int | None = None
    user_id: str = ""
    updated_at: str = ""

    def to_sheet_row(self) -> list[str | float]:
        values = asdict(self)
        order = (
            "record_date",
            "weight",
            "sleep",
            "bowel_movement",
            "energy",
            "trained",
            "training_details",
            "water",
            "diet",
            "protein",
            "notes",
            "soreness",
            "overall_score",
            "user_id",
            "updated_at",
        )
        return [
            values[key].isoformat()
            if key == "record_date"
            else ""
            if values[key] is None
            else values[key]
            for key in order
        ]

    @classmethod
    def from_sheet_row(cls, row: dict[str, str]) -> DailyRecord:
        def number(name: str, cast=float):
            value = row.get(name, "").strip()
            return cast(float(value)) if value else None

        return cls(
            record_date=date.fromisoformat(row["日期"]),
            weight=number("晨重"),
            sleep=number("睡眠"),
            bowel_movement=row.get("排便", ""),
            energy=number("精神", int),
            trained=row.get("训练", ""),
            training_details=row.get("训练详情", ""),
            water=number("饮水"),
            diet=row.get("饮食", ""),
            protein=number("蛋白质估算"),
            notes=row.get("备注", ""),
            soreness=row.get("酸痛", ""),
            overall_score=number("综合评分", int),
            user_id=row.get("用户ID", ""),
            updated_at=row.get("更新时间", ""),
        )
