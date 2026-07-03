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
