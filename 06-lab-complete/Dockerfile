# ============================================================
# TODO (tiêu chí 1): viết lại thành Dockerfile production
#   • Multi-stage build: stage builder cài dependencies, stage runtime chỉ copy kết quả
#   • Base image slim (vd python:3.11-slim) và chạy bằng user non-root
#   • Có HEALTHCHECK gọi GET /health
#   • Image cuối < 500 MB
#   • CMD lắng nghe theo biến PORT (mặc định 8000) và uvicorn phải là PID 1
#     (exec form, hoặc `sh -c "exec uvicorn ..."`) để nhận SIGTERM khi `docker stop`
#
# Bản dưới đây build và chạy được nhưng CHƯA đạt yêu cầu nào ở trên.
# ============================================================
# STAGE 1: Builder
FROM python:3.12-slim AS builder

WORKDIR /app

RUN python -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt


# STAGE 2: Runtime
FROM python:3.12-slim AS runtime

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser utils/ ./utils/

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/health', timeout=3)" || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --timeout-graceful-shutdown 8"]
