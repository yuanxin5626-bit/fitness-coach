# AI Fitness Coach

一个面向长期维护的 LINE 健身教练机器人。每天收集体重、睡眠、训练、饮水、饮食和酸痛数据，写入 Google Sheets，自动分析并生成可直接复制给 ChatGPT 的日报，以及带折线图的周报。

目标配置默认为：身高 177cm、起始体重约 91kg、2026-09-01 前低于 85kg、蛋白质 130g/天、饮水 3L/天。

## 已实现功能

- LINE Messaging API Webhook、签名校验、关注用户自动登记
- 07:30 晨间提醒、22:00 晚间提醒、周日 22:30 周报（Asia/Tokyo）
- GitHub Actions 免费外部定时唤醒，兼容 Render 免费实例休眠
- Google Sheets 自动建表、同日数据合并更新
- 晨间与晚间文本校验、自然标签格式解析
- 蛋白质规则估算（保守估计，后续可替换为 OpenAI）
- 7/30 日平均体重、累计下降、目标差距、连续打卡等统计
- 睡眠、饮水、训练、蛋白质和 7 日体重趋势提醒
- 固定格式《ChatGPT日报》
- 周报与体重/睡眠/饮水 PNG 折线图
- Docker、Render Blueprint、健康检查、自动测试

## 项目结构

```text
app/
  main.py          FastAPI 与 LINE Webhook
  coach.py         对话编排与记录合并
  storage.py       Google Sheets / 测试内存存储
  parsers.py       输入解析和蛋白质估算
  analytics.py     指标、提醒和教练分析
  reports.py       日报、周报、图表
  scheduler.py     定时任务
  line_client.py   LINE 消息适配层
tests/             单元与流程测试
```

## 1. 创建 Google Sheet

1. 在 Google Cloud 创建项目，启用 **Google Sheets API**。
2. 创建 Service Account，下载 JSON 密钥。
3. 新建一个空 Google Sheet，从网址复制表格 ID：`/spreadsheets/d/<这里是ID>/edit`。
4. 把该 Sheet 共享给 JSON 中的 `client_email`，权限设为编辑者。
5. 本地把密钥保存为项目根目录 `service-account.json`。不要提交到 Git。

应用首次连接会自动创建“每日记录”和“用户”工作表及字段。

## 2. 创建 LINE Bot

1. 在 [LINE Developers Console](https://developers.line.biz/console/) 创建 Provider 和 Messaging API Channel。
2. 在 Messaging API 页签签发 Channel access token。
3. 复制 Basic settings 中的 Channel secret。
4. 关闭 LINE 官方后台的自动回复，避免一条消息收到两次回复。
5. 部署后把 Webhook URL 设置为 `https://你的域名/webhook`，点击 Verify，再启用 Webhook。

用户第一次关注或发送消息后会自动登记到“用户”工作表，随后收到定时提醒。

## 3. 本地运行

需要 Python 3.12+。

```powershell
cd D:\codex工作文件夹\fitness-coach
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
# 填写 .env 后启动
uvicorn app.main:app --reload --port 8000
```

健康检查：`http://localhost:8000/health`。LINE 无法访问 localhost；本地联调可用 Cloudflare Tunnel 或 ngrok 暴露 8000 端口。

未配置 Google Sheet 时，开发环境会使用内存存储，重启后数据消失；生产环境会拒绝以此方式启动。

## 4. 配置 `.env`

最少需要：

```dotenv
LINE_CHANNEL_SECRET=...
LINE_CHANNEL_ACCESS_TOKEN=...
GOOGLE_SHEET_ID=...
GOOGLE_SERVICE_ACCOUNT_FILE=service-account.json
BASE_URL=http://localhost:8000
TIMEZONE=Asia/Tokyo
```

Render 上不要上传密钥文件。把完整 JSON 压成一行，保存到 Secret 环境变量 `GOOGLE_SERVICE_ACCOUNT_JSON`。`BASE_URL` 必须是 Render 的公开 HTTPS 地址，LINE 才能读取周报图片。

## 5. 部署到 Render

1. 将项目推送到 GitHub/GitLab。
2. Render Dashboard 选择 **New > Blueprint**，选中仓库；`render.yaml` 会创建 Docker Web Service。
3. 在 Render 填写所有标记为 `sync: false` 的 Secret。
4. 首次部署成功后更新 `BASE_URL`，再把 `/webhook` 地址填入 LINE Console。
5. 保持单实例、单 worker。零月费部署把 `ENABLE_SCHEDULER` 设为 `false`，由 GitHub Actions 触发，避免休眠导致漏发。

### 零月费定时提醒

仓库已包含 `.github/workflows/reminders.yml`。在 GitHub 仓库的 **Settings > Secrets and variables > Actions** 添加：

- `RENDER_BASE_URL`：例如 `https://fitness-coach.onrender.com`
- `CRON_SECRET`：与 Render 中的 `CRON_SECRET` 完全相同，建议使用至少 32 位随机字符串

GitHub Actions 使用 UTC，工作流已换算日本时间。Render 免费实例休眠时，首次唤醒通常约需一分钟；GitHub 的免费定时任务也没有严格准点 SLA，所以提醒偶尔可能延后几分钟，但不会因为应用休眠而永久漏掉。

> Render Free Web Service 闲置 15 分钟后休眠。本项目的 GitHub Actions 会发 HTTP 请求唤醒它并执行任务，因此不需要付费常驻实例。

## 使用方法

机器人命令：`晨间`、`晚间`、`日报`、`周报`、`统计`、`帮助`。

晨间数据按四行发送：

```text
90.6
6.5
是
5
```

晚间建议保留标签：

```text
Push
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
酸痛：
胸2
肩3
状态：7
```

蛋白质是关键词与份量规则估算，不等同于营养师核算。食物未写克数时只有少数常见套餐会采用默认值。

## 测试与代码检查

```powershell
pytest -q
ruff check .
```

## 后续扩展位置

- OpenAI 分析：新增 `app/analyzers/openai.py`，实现与 `coaching_analysis` 等价的接口，并在 `CoachService` 注入。
- 图片识别：在 Webhook 增加 ImageMessage 处理器，把结果写入新的“体型记录”工作表。
- 腰围/体脂：给 `DailyRecord`、`SHEET_HEADERS` 和迁移逻辑增加字段。
- Telegram：新增消息适配器，复用 `CoachService`、Storage、Reports，不需要重写业务层。
- 自动调计划：根据 48 小时酸痛峰值、左腿旧伤、训练历史，独立实现 `TrainingPlanner`。

## 安全与维护

- `.env`、Service Account JSON 已加入 `.gitignore`。
- LINE 请求必须通过签名校验。
- 健身建议仅用于日常记录，不替代医生、康复师或营养师；左腿出现疼痛、肿胀或功能受限时应停止训练并就医。
- 修改 Google Sheets 表头前，应同步更新 `app/models.py`；建议先备份表格。
