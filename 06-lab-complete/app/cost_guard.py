"""Atomic daily budget reservations for the mock LLM request path."""

from datetime import datetime, timezone
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006
_RESERVATION_TTL_SECONDS = 172800

_RESERVE_SCRIPT = """
-- RESERVE_BUDGET
local total = tonumber(redis.call('GET', KEYS[1]) or '0')
local reserve = tonumber(ARGV[1])
if total + reserve > tonumber(ARGV[2]) then return 0 end
redis.call('INCRBYFLOAT', KEYS[1], reserve)
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
redis.call('HSET', KEYS[2], 'day_key', KEYS[1], 'reserved', reserve, 'state', 'reserved')
redis.call('EXPIRE', KEYS[2], tonumber(ARGV[3]))
return 1
"""

_SETTLE_SCRIPT = """
-- SETTLE_BUDGET
local state = redis.call('HGET', KEYS[1], 'state')
if not state then return -1 end
if state == 'settled' then return 2 end
if state ~= 'reserved' then return -1 end
local reserved = tonumber(redis.call('HGET', KEYS[1], 'reserved'))
local actual = tonumber(ARGV[1])
if actual > reserved then return 0 end
local day_key = redis.call('HGET', KEYS[1], 'day_key')
redis.call('INCRBYFLOAT', day_key, actual - reserved)
redis.call('HSET', KEYS[1], 'state', 'settled', 'actual', actual)
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
return 1
"""

_RELEASE_SCRIPT = """
-- RELEASE_BUDGET
local state = redis.call('HGET', KEYS[1], 'state')
if state == 'reserved' then
  local day_key = redis.call('HGET', KEYS[1], 'day_key')
  local reserved = tonumber(redis.call('HGET', KEYS[1], 'reserved'))
  redis.call('INCRBYFLOAT', day_key, -reserved)
  redis.call('HSET', KEYS[1], 'state', 'released')
  redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
return 1
"""


def _daily_key() -> str:
    return f"cost:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"


def _reservation_key(reservation_id: str) -> str:
    return f"cost:reservation:{reservation_id}"


def _cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * PRICE_INPUT_PER_1K + output_tokens * PRICE_OUTPUT_PER_1K) / 1000


def _require_redis():
    if r is None:
        raise HTTPException(status_code=503, detail="Cost guard unavailable")
    return r


def reserve_budget(input_tokens: int) -> str:
    """Reserve input estimate and the full configured output cap atomically."""
    if input_tokens < 0:
        raise ValueError("input_tokens must be non-negative")
    reservation_id = uuid.uuid4().hex
    reserve = _cost(input_tokens, settings.max_output_tokens)
    try:
        accepted = _require_redis().eval(
            _RESERVE_SCRIPT,
            2,
            _daily_key(),
            _reservation_key(reservation_id),
            reserve,
            settings.daily_budget_usd,
            _RESERVATION_TTL_SECONDS,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Cost guard unavailable") from exc
    if not accepted:
        raise HTTPException(status_code=402, detail="Daily budget exceeded")
    return reservation_id


def settle_budget(reservation_id: str, input_tokens: int, output_tokens: int) -> float:
    """Settle a reservation once; repeated settlements do not change totals."""
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("token counts must be non-negative")
    if output_tokens > settings.max_output_tokens:
        raise HTTPException(status_code=402, detail="Maximum output tokens exceeded")
    actual = _cost(input_tokens, output_tokens)
    try:
        result = _require_redis().eval(
            _SETTLE_SCRIPT,
            1,
            _reservation_key(reservation_id),
            actual,
            _RESERVATION_TTL_SECONDS,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Cost guard unavailable") from exc
    if result == 0:
        raise HTTPException(status_code=402, detail="Actual cost exceeds reserved amount")
    if result == -1:
        raise HTTPException(status_code=503, detail="Budget reservation unavailable")
    return actual


def release_budget(reservation_id: str) -> None:
    """Release a held reservation; terminal release calls are idempotent."""
    try:
        _require_redis().eval(
            _RELEASE_SCRIPT,
            1,
            _reservation_key(reservation_id),
            _RESERVATION_TTL_SECONDS,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Cost guard unavailable") from exc


# Transitional compatibility for the API migration task; removed once /ask uses reservations.
def check_budget() -> None:
    if r is None:
        raise HTTPException(status_code=503, detail="Cost guard unavailable")
    try:
        current = float(r.get(_daily_key()) or 0)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Cost guard unavailable") from exc
    if current >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily budget exceeded")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    raise HTTPException(status_code=503, detail="Use budget reservation settlement")
