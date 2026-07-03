from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhook import WebhookParser
from linebot.v3.webhooks import FollowEvent, MessageEvent, TextMessageContent

from app.coach import CoachService
from app.config import get_settings
from app.line_client import LineClient
from app.messages import WELCOME
from app.scheduler import CoachScheduler
from app.storage import build_storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()
storage = build_storage(settings)
line = LineClient(settings.line_channel_access_token)
coach = CoachService(storage, settings)
parser = WebhookParser(settings.line_channel_secret) if settings.line_channel_secret else None
scheduler = CoachScheduler(storage, line, coach, settings)
Path("reports").mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.enable_scheduler:
        scheduler.start()
    if settings.default_line_user_id:
        storage.register_user(settings.default_line_user_id)
    yield
    scheduler.stop()


app = FastAPI(title="AI Fitness Coach", version="1.0.0", lifespan=lifespan)
app.mount("/reports", StaticFiles(directory="reports"), name="reports")


@app.get("/")
def root():
    return {"name": "AI Fitness Coach", "status": "running", "docs": "/docs"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "storage": storage.__class__.__name__,
        "scheduler": settings.enable_scheduler,
    }


@app.post("/tasks/{job_name}")
def run_scheduled_job(job_name: str, x_cron_secret: str = Header(default="")):
    """Authenticated endpoint used by free external schedulers to wake Render."""
    if not settings.cron_secret or x_cron_secret != settings.cron_secret:
        raise HTTPException(401, "Invalid cron secret")
    jobs = {
        "morning": scheduler.morning,
        "evening": scheduler.evening,
        "weekly": scheduler.weekly,
    }
    job = jobs.get(job_name)
    if not job:
        raise HTTPException(404, "Unknown scheduled job")
    job()
    return {"ok": True, "job": job_name}


@app.post("/webhook")
async def webhook(request: Request, x_line_signature: str = Header(default="")):
    if not parser:
        raise HTTPException(503, "LINE_CHANNEL_SECRET is not configured")
    body = (await request.body()).decode("utf-8")
    try:
        events = parser.parse(body, x_line_signature)
    except InvalidSignatureError as exc:
        raise HTTPException(400, "Invalid LINE signature") from exc
    for event in events:
        user_id = getattr(event.source, "user_id", "")
        if not user_id:
            continue
        if isinstance(event, FollowEvent):
            storage.register_user(user_id)
            line.reply(event.reply_token, WELCOME)
        elif isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            try:
                line.reply(event.reply_token, coach.handle_text(user_id, event.message.text))
            except Exception:
                logger.exception("Failed to handle message for user %s", user_id)
                line.reply(
                    event.reply_token,
                    "保存时遇到问题，请稍后重试。若持续失败，请检查 Google Sheets 配置。",
                )
    return JSONResponse({"ok": True})
