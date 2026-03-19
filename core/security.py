from __future__ import annotations

import time
from typing import TYPE_CHECKING
from typing import cast

from django.conf import settings
from django.core.cache import cache

from .errors import build_error

if TYPE_CHECKING:
    from datetime import timedelta

    from django.http import HttpRequest
    from ninja_jwt.tokens import RefreshToken

    from .schemas import ErrorResponse


def get_client_ip(request: HttpRequest) -> str:
    """提取客户端 IP，优先使用反向代理转发头。"""
    forwarded_for = request.headers.get("X-Forwarded-For", "").strip()
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    remote_addr = request.META.get("REMOTE_ADDR")
    if isinstance(remote_addr, str) and remote_addr:
        return remote_addr
    return "unknown"


def check_rate_limit(
    *,
    scope: str,
    identifier: str,
    limit: int,
    window_seconds: int,
    request_id: str,
) -> ErrorResponse | None:
    """使用固定窗口计数器执行轻量限流。"""
    if limit <= 0 or window_seconds <= 0:
        return None

    bucket = int(time.time()) // window_seconds
    cache_key = f"{settings.RATE_LIMIT_CACHE_PREFIX}:{scope}:{identifier}:{bucket}"
    current_count = 1 if cache.add(cache_key, 1, timeout=window_seconds + 1) else int(cache.incr(cache_key))

    if current_count > limit:
        return build_error(detail="请求过于频繁, 请稍后再试", code="RATE_LIMIT_EXCEEDED", request_id=request_id)
    return None


def refresh_token_is_revoked(refresh_token: RefreshToken) -> bool:
    """检查 Refresh Token 是否已被标记失效。"""
    jti = str(refresh_token.get("jti", "")).strip()
    if not jti:
        return False

    cache_key = f"{settings.RATE_LIMIT_CACHE_PREFIX}:revoked-refresh:{jti}"
    return bool(cache.get(cache_key, False))


def revoke_user_refresh_tokens(user_id: int) -> None:
    if user_id <= 0:
        return

    cache_key = f"{settings.RATE_LIMIT_CACHE_PREFIX}:revoked-refresh-before:{user_id}"
    now = int(time.time())
    refresh_token_lifetime = cast("timedelta", settings.NINJA_JWT["REFRESH_TOKEN_LIFETIME"])
    refresh_lifetime = int(refresh_token_lifetime.total_seconds())
    cache.set(cache_key, value=now, timeout=refresh_lifetime + 60)


def refresh_token_revoked_by_user(refresh_token: RefreshToken) -> bool:
    user_id_claim = cast("str", settings.NINJA_JWT["USER_ID_CLAIM"])
    user_id = refresh_token.get(user_id_claim)
    if not isinstance(user_id, int) or user_id <= 0:
        return False

    cache_key = f"{settings.RATE_LIMIT_CACHE_PREFIX}:revoked-refresh-before:{user_id}"
    revoked_before = cache.get(cache_key)
    if not isinstance(revoked_before, int) or revoked_before <= 0:
        return False

    iat = refresh_token.get("iat")
    if not isinstance(iat, int):
        return True
    return iat <= revoked_before


def revoke_refresh_token(refresh_token: RefreshToken) -> None:
    """将已使用的 Refresh Token 标记为失效，直到其自然过期。"""
    jti = str(refresh_token.get("jti", "")).strip()
    exp = refresh_token.get("exp")
    if not jti or not isinstance(exp, int):
        return

    timeout = max(exp - int(time.time()), 1)
    cache_key = f"{settings.RATE_LIMIT_CACHE_PREFIX}:revoked-refresh:{jti}"
    cache.set(cache_key, value=1, timeout=timeout)
