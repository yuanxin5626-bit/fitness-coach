from datetime import date, timedelta

from app.intent_router import extract_water_liters, route_message


def test_water_natural_language_units():
    assert extract_water_liters("今天喝了两升水") == 2
    assert extract_water_liters("目前1500ml") == 1.5
    assert extract_water_liters("2L水") == 2


def test_yesterday_and_multiple_intents():
    today = date(2026, 7, 3)
    routed = route_message("昨天客户请吃烤肉，喝了五杯酒，没训练", today)
    assert routed.day == today - timedelta(days=1)
    assert {"social", "diet", "training"} <= routed.intents


def test_query_has_priority():
    routed = route_message("最近30天", date(2026, 7, 3))
    assert routed.intents == {"query"}
