import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def allowed(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            timestamps = [t for t in self._requests[key] if t > cutoff]
            self._requests[key] = timestamps
            if len(timestamps) >= self.max_requests:
                return False
            timestamps.append(now)
            return True

    def clear(self) -> None:
        with self._lock:
            self._requests.clear()


def _client_host(request: Request) -> str:
    host = request.client.host if request.client else None
    return host or "unknown"


def check_rate_limit(limiter: RateLimiter, key: str) -> None:
    if not limiter.allowed(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
        )


def ip_enforce(limiter: RateLimiter, request: Request) -> None:
    check_rate_limit(limiter, _client_host(request))


register_ip = RateLimiter(max_requests=10, window_seconds=60)
login_ip = RateLimiter(max_requests=30, window_seconds=60)
login_email = RateLimiter(max_requests=5, window_seconds=60)
chat_ip = RateLimiter(max_requests=20, window_seconds=60)
