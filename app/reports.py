from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import matplotlib

from app.analytics import avg, coaching_analysis, is_training
from app.models import DailyRecord

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = ["Noto Sans CJK JP", "Microsoft YaHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False


def _value(value, suffix: str = "", empty: str = "未记录") -> str:
    return f"{value}{suffix}" if value is not None and value != "" else empty


def daily_report(record: DailyRecord, history: list[DailyRecord]) -> str:
    bowel = (
        "已排便"
        if record.bowel_movement == "是"
        else "未排便"
        if record.bowel_movement
        else "未记录"
    )
    analysis = "\n".join(coaching_analysis(record, history)) or "数据不足，完成记录后会自动分析。"
    return f"""--------------------------------
{record.record_date.isoformat()}

【晨间数据】
体重：{_value(record.weight, "kg")}
睡眠：{_value(record.sleep, "h")}
排便：{bowel}
精神：{_value(record.energy, "/10")}

--------------------------------
【训练】
{record.trained or "未记录"}
{record.training_details or ""}

--------------------------------
【饮食】
{record.diet or "未记录"}

--------------------------------
【蛋白质估算】
{_value(record.protein, "g")}

--------------------------------
【饮水】
{_value(record.water, "L")}

--------------------------------
【酸痛】
{record.soreness or "无/未记录"}

--------------------------------
【备注】
{record.notes or "无"}

--------------------------------
【机器人分析】
{analysis}

建议：
以恢复质量为优先；背部、上胸与核心训练循序渐进，左腿不适时立即降低强度。
--------------------------------
（这一整段可以直接复制给ChatGPT。）"""


def weekly_report(records: list[DailyRecord], end: date | None = None) -> str:
    end = end or date.today()
    start = end - timedelta(days=6)
    week = [r for r in records if start <= r.record_date <= end]
    weights = [r.weight for r in week if r.weight is not None]
    decline = round(weights[0] - weights[-1], 2) if len(weights) >= 2 else 0
    complete = sum(
        bool(r.weight is not None and r.sleep is not None and r.water is not None) for r in week
    )
    return f"""📊 Fitness Coach 周报
{start.isoformat()} ～ {end.isoformat()}

平均体重：{_value(avg([r.weight for r in week]), "kg")}
本周下降：{decline}kg
训练次数：{sum(is_training(r) for r in week)}次
平均睡眠：{_value(avg([r.sleep for r in week]), "h")}
平均饮水：{_value(avg([r.water for r in week]), "L")}
蛋白质平均值：{_value(avg([r.protein for r in week]), "g")}
完成率：{round(complete / 7 * 100)}%

目标：2026-09-01 前低于 85kg。稳定的小幅下降比极端节食更适合长期保持。"""


def create_weekly_charts(records: list[DailyRecord], output_dir: Path, user_id: str) -> list[Path]:
    week = sorted(records, key=lambda r: r.record_date)[-7:]
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_user = "".join(c for c in user_id if c.isalnum())[-12:] or "user"
    charts = [
        ("weight", "体重趋势", "kg", [r.weight for r in week]),
        ("sleep", "睡眠趋势", "小时", [r.sleep for r in week]),
        ("water", "饮水趋势", "L", [r.water for r in week]),
    ]
    paths: list[Path] = []
    labels = [r.record_date.strftime("%m-%d") for r in week]
    for key, title, unit, values in charts:
        if not any(v is not None for v in values):
            continue
        path = output_dir / f"{safe_user}-{key}.png"
        fig, ax = plt.subplots(figsize=(9, 4.8))
        ax.plot(labels, values, marker="o", linewidth=2.3, color="#2f80ed")
        ax.set_title(title, fontsize=16)
        ax.set_ylabel(unit)
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths
