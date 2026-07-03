import pytest

from app.parsers import ParseError, estimate_protein, parse_evening, parse_morning


def test_parse_morning():
    data = parse_morning("90.6\n6.5\n是\n5")
    assert data.weight == 90.6
    assert data.sleep == 6.5
    assert data.bowel_movement == "是"
    assert data.energy == 5


def test_morning_validation():
    with pytest.raises(ParseError):
        parse_morning("90\n6\n是\n15")


def test_parse_evening_example():
    text = """Push
卧推40×8×4
饮水2.8L
早餐：
鸡蛋3
牛奶500ml
蛋白粉28g
午餐：
牛肉饭
晚餐：
鲑鱼100g
黄瓜
酸痛：
胸2
肩3
状态：
7"""
    data = parse_evening(text)
    assert data.trained == "Push"
    assert data.water == 2.8
    assert data.overall_score == 7
    assert "牛肉饭" in data.diet
    assert "胸2" in data.soreness
    assert estimate_protein(data.diet) > 90
