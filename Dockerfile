FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY migrations ./migrations
COPY alembic.ini ./
COPY scripts ./scripts

EXPOSE 8000

# 启动时自动迁移；需在 .env / 环境变量里提供 MySQL 与 provider key
CMD ["sh", "-c", "alembic upgrade head && uvicorn anchorline.api.main:app --host 0.0.0.0 --port 8000"]
