"""
Production AI Agent — Part 6 Final Project (bản khung)

Hoàn thành các TODO để đạt đủ 12 tiêu chí trong README.md, rồi kiểm tra:
    python check_production_ready.py

Bản khung này chạy được (uvicorn app.main:app) nhưng chưa đạt tiêu chí nào.
"""
import logging
from contextlib import asynccontextmanager
import json
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException, Depends
from pydantic import BaseModel, Field

from utils.mock_llm import ask as llm_ask
from app.config import settings
from app.redis_client import redis_healthy, r
from app.auth import verify_api_key
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_budget, record_cost

# TODO (tiêu chí 10 — Structured logging):
#   Mỗi dòng log của app phải là 1 JSON object hợp lệ, vd
#   {"ts": "...", "lvl": "INFO", "event": "request", "path": "/ask", "status": 200, "ms": 12.3}
#   Gợi ý: tự viết logging.Formatter dùng json.dumps.
class JSONFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "event": record.getMessage(),
        }

        for field in ("path", "method", "status", "ms"):
            if hasattr(record, field):
                payload[field] = getattr(record, field)

        return json.dumps(payload, ensure_ascii=False)


handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.handlers.clear()
logger.addHandler(handler)
logger.propagate = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup")

    try:
        yield
    finally:
        logger.info("graceful_shutdown_started")

        r.close()

        logger.info("graceful_shutdown_complete")


app = FastAPI(
    title="Production AI Agent",
    lifespan=lifespan,
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


# TODO (tiêu chí 4): GET /health — liveness: luôn trả 200 khi process còn chạy
#                    (kể cả khi Redis chưa kết nối được)
# TODO (tiêu chí 5): GET /ready  — readiness: 200 khi sẵn sàng, 503 khi Redis không kết nối được




START_TIME = time.monotonic()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    status = 500

    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        logger.info(
            "request",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status": status,
                "ms": round(
                    (time.perf_counter() - started) * 1000, 2
                ),
            },
        )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "environment": settings.environment,
        "uptime_seconds": round(
            time.monotonic() - START_TIME, 2
        ),
    }

@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(
            status_code=503,
            detail="Redis unavailable"
        )

    return {
        "ready": True,
        "redis_connected": True,
    }


@app.post("/ask")
def ask(
    body: AskRequest,
    api_key: str = Depends(verify_api_key),
):
    # TODO (tiêu chí 6): bắt buộc header X-API-Key → thêm Depends(verify_api_key)
    # TODO (tiêu chí 7): check_rate_limit(...) → 429 khi vượt giới hạn
    # TODO (tiêu chí 8): check_budget() trước khi gọi LLM, record_cost(...) sau khi gọi → 402 khi hết budget
    check_rate_limit(api_key)
    check_budget()

    answer = llm_ask(body.question)

    # Estimate token usage for Mock LLM
    input_tokens = max(1, len(body.question.split()))
    output_tokens = max(1, len(answer.split()))

    cost = record_cost(input_tokens, output_tokens)

    return {
        "question": body.question,
        "answer": answer,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 10),
        },
    }


# TODO (tiêu chí 11 — Graceful shutdown):
#   Khi nhận SIGTERM: ngừng nhận request mới, xử lý xong request đang chạy rồi thoát (exit code 0).
#   Gợi ý: dùng lifespan của FastAPI để dọn dẹp. Nếu tự đăng ký signal handler cho SIGTERM thì
#   phải gọi lại handler cũ của uvicorn, nếu không process sẽ không bao giờ tắt.
