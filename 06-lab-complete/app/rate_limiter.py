"""
Rate limiting (tiêu chí 7).

Yêu cầu:
  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, nên kèm header Retry-After
  • State lưu trong Redis để mọi worker / instance dùng chung và vẫn còn sau khi
    restart agent (script chấm sẽ restart agent để kiểm tra)
"""

import time
import uuid
import hashlib

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

_SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local cutoff = tonumber(ARGV[2])
local member = ARGV[3]
local limit = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])
redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
if redis.call('ZCARD', key) >= limit then
  return 0
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, ttl)
return 1
"""

def check_rate_limit(key: str) -> None:
    if r is None:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable")
    now = time.time()
    key_digest = hashlib.sha256(key.encode()).hexdigest()
    try:
        allowed = r.eval(
            _SLIDING_WINDOW_SCRIPT,
            1,
            f"rate:{key_digest}",
            now,
            now - 60,
            f"{now}:{uuid.uuid4().hex}",
            settings.rate_limit_per_minute,
            120,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable") from exc
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers={"Retry-After": "60"})
