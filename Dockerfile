FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY pyproject.toml README.md ./
COPY shopilot ./shopilot
COPY alembic.ini ./
COPY alembic ./alembic
RUN python -m pip install --prefix=/install .

FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SHOPILOT_HOST=0.0.0.0 \
    SHOPILOT_PORT=8000 \
    SHOPILOT_DATA_DIR=/app/data

RUN groupadd --system --gid 10001 shopilot \
    && useradd --system --uid 10001 --gid shopilot --home-dir /app shopilot \
    && mkdir -p /app/data \
    && chown -R shopilot:shopilot /app
COPY --from=builder /install /usr/local
COPY alembic.ini ./
COPY alembic ./alembic
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('SHOPILOT_PORT','8000')+'/health/live',timeout=2)"
CMD ["shopilot-server"]

