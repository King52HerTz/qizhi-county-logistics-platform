FROM python:3.12-slim AS runtime

ARG QIZHI_PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=600 \
    PIP_RETRIES=12 \
    PIP_INDEX_URL=${QIZHI_PIP_INDEX_URL}

WORKDIR /app
COPY pyproject.toml ./
RUN mkdir -p app \
    && touch app/__init__.py \
    && pip install --disable-pip-version-check --default-timeout=600 --retries=12 . \
    && rm -rf app

COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
RUN pip install . --no-deps

RUN useradd --create-home --uid 10001 qizhi && chown -R qizhi:qizhi /app
USER qizhi

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
