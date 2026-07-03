from app.coach import CoachService
from app.config import Settings
from app.storage import MemoryStorage


def test_full_checkin():
    storage = MemoryStorage()
    coach = CoachService(storage, Settings(enable_scheduler=False))
    user = "U123"
    coach.handle_text(user, "晨间")
    result = coach.handle_text(user, "90.6\n6.5\n是\n5")
    assert "已保存" in result
    coach.handle_text(user, "晚间")
    result = coach.handle_text(
        user, "Push\n卧推40×8×4\n饮水2.8L\n早餐：\n鸡蛋3\n酸痛：\n胸2\n状态：7"
    )
    assert "ChatGPT日报" in result
    assert storage.get_record(user, coach.today()).weight == 90.6


def test_food_is_saved_without_morning_checkin():
    storage = MemoryStorage()
    coach = CoachService(storage, Settings(enable_scheduler=False))
    result = coach.handle_text("U-food", "早餐：鸡蛋3\n牛奶500ml")
    record = storage.get_record("U-food", coach.today())
    assert "饮食已记录" in result
    assert "鸡蛋3" in record.diet
    assert record.weight is None


def test_food_overrides_pending_morning_phase_and_morning_can_be_backfilled():
    storage = MemoryStorage()
    coach = CoachService(storage, Settings(enable_scheduler=False))
    user = "U-flex"
    coach.handle_text(user, "晨间")
    assert "饮食已记录" in coach.handle_text(user, "午餐：牛肉饭")
    assert "晨间数据已保存" in coach.handle_text(user, "90.6\n6.5\n是\n5")
    record = storage.get_record(user, coach.today())
    assert "牛肉饭" in record.diet
    assert record.weight == 90.6


def test_training_and_bedtime_events_are_non_blocking():
    storage = MemoryStorage()
    coach = CoachService(storage, Settings(enable_scheduler=False))
    user = "U-train"
    assert "开始记录" in coach.handle_text(user, "开始训练")
    assert "训练内容已追加" in coach.handle_text(user, "卧推40×8×4")
    assert "训练完成" in coach.handle_text(user, "训练完成")
    assert "饮食已记录" in coach.handle_text(user, "晚餐：鲑鱼100g")
    assert "睡前总结" in coach.handle_text(user, "准备睡觉")


def test_yesterday_water_backfill_and_natural_morning():
    storage = MemoryStorage()
    coach = CoachService(storage, Settings(enable_scheduler=False))
    user = "U-backfill"
    assert "饮水 2.8L" in coach.handle_text(user, "昨天喝了2.8L")
    yesterday = coach.today() - __import__("datetime").timedelta(days=1)
    assert storage.get_record(user, yesterday).water == 2.8
    coach.handle_text(user, "体重90.6，睡眠6.5，已排便，精神5")
    record = storage.get_record(user, coach.today())
    assert record.weight == 90.6
    assert record.energy == 5


def test_multi_intent_social_meal_and_cancelled_training():
    storage = MemoryStorage()
    coach = CoachService(storage, Settings(enable_scheduler=False))
    user = "U-social"
    result = coach.handle_text(user, "今天客户请吃烤肉，喝了五杯酒，没训练")
    record = storage.get_record(user, coach.today())
    assert all(word in result for word in ("饮食", "应酬", "训练"))
    assert record.trained == "否"
    assert "烤肉" in record.diet
    assert "客户" in record.social


def test_unknown_free_text_is_preserved_as_note():
    storage = MemoryStorage()
    coach = CoachService(storage, Settings(enable_scheduler=False))
    result = coach.handle_text("U-note", "今天工作节奏完全打乱了")
    assert "备注" in result
    assert "工作节奏" in storage.get_record("U-note", coach.today()).notes
