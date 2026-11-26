"""
Rate limiting (tiêu chí 7).

Yêu cầu:
  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, nên kèm header Retry-After
  • State lưu trong Redis để mọi worker / instance dùng chung và vẫn còn sau khi
    restart agent (script chấm sẽ restart agent để kiểm tra)
"""


import hashlib
import math
from uuid import uuid4

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r


RATE_LIMIT_SCRIPT = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) + tonumber(clock[2]) / 1000000
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])

redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)

local count = redis.call('ZCARD', KEYS[1])

if count >= limit then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    local retry = math.ceil(window - (now - tonumber(oldest[2])))
    return {0, math.max(1, retry)}
end

redis.call('ZADD', KEYS[1], now, ARGV[3])
redis.call('EXPIRE', KEYS[1], window)

return {1, 0}
"""


def check_rate_limit(key: str) -> None:
    # TODO: gợi ý dùng Redis sorted set: ZREMRANGEBYSCORE → ZCARD → ZADD → EXPIRE
    key_hash = hashlib.sha256(
        key.encode("utf-8")
    ).hexdigest()

    redis_key = f"day14:rate_limit:{key_hash}"

    if settings.rate_limit_per_minute <= 0:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"},
        )

    try:
        allowed, retry_after = r.eval(
            RATE_LIMIT_SCRIPT,
            1,
            redis_key,
            60,
            settings.rate_limit_per_minute,
            uuid4().hex,
        )
    except redis.RedisError:
        raise HTTPException(
            status_code=503,
            detail="Redis unavailable",
        )

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(retry_after)
            },
        )
