FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p reports
EXPOSE 8000
CMD ["sh", "-c", "python -m uvicorn app.main:app --app-dir /app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
