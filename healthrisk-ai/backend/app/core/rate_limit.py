import time
import logging
from typing import Tuple, Optional, Dict
from fastapi import Request, HTTPException, status
from app.core.config import settings

logger = logging.getLogger("healthrisk.ratelimit")

# In-memory sliding window store as robust fallback when Redis is absent
_in_memory_windows: Dict[str, list] = {}
_in_memory_lockouts: Dict[str, dict] = {}

# Try Redis connection gracefully
_redis_client = None
try:
    import redis
    _r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1)
    _r.ping()
    _redis_client = _r
    logger.info("Connected to Redis successfully for rate limiting.")
except Exception as e:
    logger.warning("Redis unavailable (%s); using thread-safe in-memory sliding-window limiter.", e)
    _redis_client = None

def get_client_ip(request: Request) -> str:
    """Extract client IP, taking into account standard reverse proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

class RateLimiter:
    """Sliding-window rate limiter with progressive lockout and Redis fallback."""

    @classmethod
    def check_rate_limit(
        cls, key: str, max_requests: int, window_seconds: int
    ) -> Tuple[bool, int, int]:
        """
        Check if key has exceeded max_requests in window_seconds.
        Returns: (is_allowed, remaining_requests, retry_after_seconds)
        """
        now = time.time()
        
        # 1. Try Redis sliding window via ZADD / ZREMRANGEBYSCORE
        if _redis_client:
            try:
                pipe = _redis_client.pipeline()
                pipe.zremrangebyscore(key, 0, now - window_seconds)
                pipe.zadd(key, {f"{now}-{time.time_ns()}": now})
                pipe.zcard(key)
                pipe.expire(key, window_seconds)
                _, _, count, _ = pipe.execute()
                
                if count > max_requests:
                    # calculate retry-after
                    oldest = _redis_client.zrange(key, 0, 0, withscores=True)
                    retry_after = int(oldest[0][1] + window_seconds - now) if oldest else window_seconds
                    return False, 0, max(1, retry_after)
                return True, max(0, max_requests - count), 0
            except Exception as e:
                logger.warning("Redis operation failed (%s); falling back to memory.", e)

        # 2. In-memory sliding window
        window = _in_memory_windows.get(key, [])
        cutoff = now - window_seconds
        # filter out expired timestamps
        valid_timestamps = [ts for ts in window if ts > cutoff]
        
        if len(valid_timestamps) >= max_requests:
            retry_after = int(valid_timestamps[0] + window_seconds - now)
            _in_memory_windows[key] = valid_timestamps
            return False, 0, max(1, retry_after)
            
        valid_timestamps.append(now)
        _in_memory_windows[key] = valid_timestamps
        return True, max_requests - len(valid_timestamps), 0

    @classmethod
    def check_lockout(cls, account_key: str) -> Tuple[bool, int]:
        """
        Check if account/IP is locked out.
        Returns: (is_locked_out, remaining_seconds)
        """
        now = time.time()
        
        # Check Redis
        if _redis_client:
            try:
                lock_val = _redis_client.get(f"lockout:{account_key}")
                if lock_val:
                    remaining = int(float(lock_val) - now)
                    if remaining > 0:
                        return True, remaining
            except Exception as e:
                logger.warning("Redis lockout check failed: %s", e)

        # Check in-memory
        lock_info = _in_memory_lockouts.get(account_key)
        if lock_info and "unlock_time" in lock_info:
            unlock_time = lock_info["unlock_time"]
            if now < unlock_time:
                return True, int(unlock_time - now)
            else:
                del lock_info["unlock_time"]
                
        return False, 0

    @classmethod
    def record_login_failure(cls, account_key: str) -> Tuple[int, int, bool]:
        """
        Record failed login attempt. After 5 failures: progressive lockout (15m, 30m, etc.)
        Returns: (failures_count, lockout_seconds, is_locked)
        """
        now = time.time()
        key = f"login_failures:{account_key}"
        
        # Count failures in memory / redis
        lock_info = _in_memory_lockouts.get(account_key, {"failures": 0, "lockouts_count": 0})
        lock_info["failures"] += 1
        
        if lock_info["failures"] >= settings.RATE_LIMIT_LOGIN_MAX:
            # Calculate progressive lockout: 15 min * (2 ** lockouts_count)
            multiplier = 2 ** min(lock_info["lockouts_count"], 4)
            lockout_sec = settings.LOCKOUT_DURATION_SEC * multiplier
            unlock_time = now + lockout_sec
            lock_info["unlock_time"] = unlock_time
            lock_info["lockouts_count"] += 1
            _in_memory_lockouts[account_key] = lock_info
            
            if _redis_client:
                try:
                    _redis_client.setex(f"lockout:{account_key}", lockout_sec, str(unlock_time))
                except Exception:
                    pass
            return lock_info["failures"], lockout_sec, True
            
        _in_memory_lockouts[account_key] = lock_info
        return lock_info["failures"], 0, False

    @classmethod
    def reset_login_failures(cls, account_key: str):
        """Reset failures upon successful login."""
        if account_key in _in_memory_lockouts:
            del _in_memory_lockouts[account_key]
        if _redis_client:
            try:
                _redis_client.delete(f"lockout:{account_key}")
                _redis_client.delete(f"login_failures:{account_key}")
            except Exception:
                pass

def enforce_rate_limit(request: Request, scope: str, max_requests: int, window_seconds: int):
    """Enforce rate limit or raise HTTP 429."""
    ip = get_client_ip(request)
    key = f"rate:{scope}:{ip}"
    allowed, remaining, retry_after = RateLimiter.check_rate_limit(key, max_requests, window_seconds)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Please try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)}
        )
