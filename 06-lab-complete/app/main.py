"""
Production AI Agent — Part 6 Final Project (bản khung)

Hoàn thành các TODO để đạt đủ 12 tiêu chí trong README.md, rồi kiểm tra:
    python check_production_ready.py

Bản khung này chạy được (uvicorn app.main:app) nhưng chưa đạt tiêu chí nào.
"""
import json
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.cost_guard import reserve_budget, release_budget, settle_budget
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from app.config import settings
from utils.mock_llm import ask as llm_ask

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.time(),
            "lvl": record.levelname,
            "event": getattr(record, "event", record.getMessage()),
        }
        for field in ("path", "status", "ms", "reservation_id"):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        return json.dumps(payload, ensure_ascii=False)


_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.handlers.clear()
logger.addHandler(_handler)
logger.propagate = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """ASGI lifespan hook: Uvicorn drains active requests before shutdown."""
    yield


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"status": "ready"}


@app.middleware("http")
async def log_request(request: Request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.error(
            "request",
            extra={"event": "request", "path": request.url.path, "status": 500,
                   "ms": round((time.perf_counter() - started) * 1000, 2)},
        )
        raise
    logger.info(
        "request",
        extra={"event": "request", "path": request.url.path, "status": response.status_code,
               "ms": round((time.perf_counter() - started) * 1000, 2)},
    )
    return response


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    input_tokens = max(1, len(body.question) // 4)
    reservation_id = reserve_budget(input_tokens)
    try:
        answer = llm_ask(body.question)
        output_tokens = max(1, len(answer) // 4)
        if output_tokens > settings.max_output_tokens:
            raise HTTPException(status_code=402, detail="Maximum output tokens exceeded")
        settle_budget(reservation_id, input_tokens, output_tokens)
    except Exception:
        try:
            release_budget(reservation_id)
        except HTTPException as release_error:
            logger.error(
                "budget_reservation_release_failed",
                extra={"event": "budget_reservation_release_failed", "reservation_id": reservation_id},
            )
            raise release_error
        raise
    return {"question": body.question, "answer": answer}
