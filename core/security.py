"""安全辅助逻辑: 限流与 Refresh Token 失效控制"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.cache import cache

from .schemas import ErrorResponse

if TYPE_CHECKING:
    from django.http import HttpRequest
    from ninja_jwt.tokens import RefreshToken


def get_client_ip(request: HttpRequest) -> str:
    """提取客户端 IP，优先使用反向代理转发头。"""
    forwarded_for = request.headers.get("X-Forwarded-For", "").strip()
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    remote_addr = request.META.get("REMOTE_ADDR")
    if isinstance(remote_addr, str) and remote_addr:
        return remote_addr
    return "unknown"


def check_rate_limit(scope: str, identifier: str, limit: int, window_seconds: int) -> ErrorResponse | None:
    """使用固定窗口计数器执行轻量限流。"""
    if limit <= 0 or window_seconds <= 0:
        return None

    bucket = int(time.time()) // window_seconds
    cache_key = f"{settings.RATE_LIMIT_CACHE_PREFIX}:{scope}:{identifier}:{bucket}"
    current_count = 1 if cache.add(cache_key, 1, timeout=window_seconds + 1) else int(cache.incr(cache_key))

    if current_count > limit:
        return ErrorResponse(detail="请求过于频繁, 请稍后再试", code="RATE_LIMIT_EXCEEDED")
    return None


def refresh_token_is_revoked(refresh_token: RefreshToken) -> bool:
    """检查 Refresh Token 是否已被标记失效。"""
    jti = str(refresh_token.get("jti", "")).strip()
    if not jti:
        return False

    cache_key = f"{settings.RATE_LIMIT_CACHE_PREFIX}:revoked-refresh:{jti}"
    return bool(cache.get(cache_key, False))


def revoke_refresh_token(refresh_token: RefreshToken) -> None:
    """将已使用的 Refresh Token 标记为失效，直到其自然过期。"""
    jti = str(refresh_token.get("jti", "")).strip()
    exp = refresh_token.get("exp")
    if not jti or not isinstance(exp, int):
        return

    timeout = max(exp - int(time.time()), 1)
    cache_key = f"{settings.RATE_LIMIT_CACHE_PREFIX}:revoked-refresh:{jti}"
    cache.set(cache_key, value=1, timeout=timeout)
