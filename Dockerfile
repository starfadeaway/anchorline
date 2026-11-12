FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    ANCHORLINE_ROOT=/app \
    ANCHORLINE_LANCEDB=/app/data/lancedb

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY migrations ./migrations
COPY alembic.ini ./
COPY scripts ./scripts

EXPOSE 8000

# 启动时自动迁移；需在 .env / 环境变量里提供 MySQL 与 provider key
CMD ["sh", "-c", "alembic upgrade head && uvicorn anchorline.api.main:app --host 0.0.0.0 --port 8000"]

# 注意：向量索引（data/lancedb）未打进镜像（体积 + 数据边界）。
# 容器内需挂载：docker run -v ./data/lancedb:/app/data/lancedb ...，或容器内重跑 build_facts_index.py；
# 否则 memory_search 只剩 BM25（检索会退化）。
