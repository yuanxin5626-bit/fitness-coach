from datetime import date, timedelta

from app.analytics import alerts, calculate_summary
from app.models import DailyRecord


def make_records(count=7):
    start = date(2026, 7, 1)
    return [
        DailyRecord(
            start + timedelta(days=i),
            weight=91 - i * 0.1,
            sleep=6,
            trained="Push" if i % 2 == 0 else "否",
            water=2.5,
            protein=125,
            user_id="u",
        )
        for i in range(count)
    ]


def test_summary():
    summary = calculate_summary(make_records(), goal=85)
    assert summary.average_weight_7d == 90.7
    assert summary.total_weight_loss == 0.6
    assert summary.kg_to_goal == 5.4
    assert summary.streak == 7
    assert summary.training_count == 4


def test_alerts_for_sleep():
    assert "建议今晚早点休息。" in alerts(make_records(2))


def test_no_decline_alert():
    records = make_records()
    for record in records:
        record.weight = 91
    assert any("体重没有下降" in item for item in alerts(records))
