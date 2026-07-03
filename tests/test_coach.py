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
