"""
Kết nối Redis dùng chung cho rate limiter và cost guard.

Yêu cầu:
  • Đọc REDIS_URL từ config
  • App vẫn phải KHỞI ĐỘNG ĐƯỢC khi Redis chưa sẵn sàng (đừng ping Redis lúc import)
  • redis_healthy() dùng cho GET /ready: Redis không kết nối được → False
"""

from app.config import settings

if settings.redis_url:
    import redis

    r = redis.from_url(settings.redis_url, decode_responses=True)
else:
    r = None


def redis_healthy() -> bool:
    if r is None:
        return False
    try:
        return bool(r.ping())
    except Exception:
        return False
