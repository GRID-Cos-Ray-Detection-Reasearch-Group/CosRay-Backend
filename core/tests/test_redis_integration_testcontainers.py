from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING
from typing import cast

import docker
import pytest
import redis
from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase
from django.test import override_settings
from docker.errors import APIError
from docker.errors import DockerException
from docker.errors import ImageNotFound
from testcontainers.core.container import DockerContainer

from core.security import check_rate_limit
from core.security import refresh_token_is_revoked
from core.security import refresh_token_revoked_by_user
from core.security import revoke_refresh_token
from core.security import revoke_user_refresh_tokens

if TYPE_CHECKING:
    from collections.abc import Iterator

    from ninja_jwt.tokens import RefreshToken


def _can_run_testcontainers() -> bool:
    if os.environ.get("SKIP_TESTCONTAINERS") == "1":
        return False
    if os.environ.get("CI") == "true":
        return False

    try:
        docker.from_env().ping()
    except (DockerException, OSError):
        return False

    return True


@contextmanager
def _start_redis_container_or_skip() -> Iterator[DockerContainer]:
    try:
        container_ctx = DockerContainer("redis:7.4-alpine").with_exposed_ports(6379)
        container = container_ctx.__enter__()
    except (APIError, DockerException, ImageNotFound, OSError) as exc:
        pytest.skip(f"Testcontainers unavailable in this environment: {exc}")

    try:
        yield container
    finally:
        container_ctx.__exit__(None, None, None)


def _wait_for_redis_ready_or_skip(redis_url: str) -> None:
    deadline = time.monotonic() + 30
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        try:
            if client.ping():
                client.flushdb()
                return
        except redis.RedisError as exc:
            last_error = exc
            time.sleep(0.5)
            continue
        finally:
            client.close()

    pytest.skip(f"Redis was not ready: {last_error}")


def _build_refresh_token_payload(user_id: int) -> RefreshToken:
    now = int(time.time())
    return cast(
        "RefreshToken",
        {
            "jti": "redis-test-jti",
            "exp": now + 3600,
            "iat": now,
            settings.NINJA_JWT["USER_ID_CLAIM"]: user_id,
        },
    )


@pytest.mark.skipif(not _can_run_testcontainers(), reason="Testcontainers requires local container runtime")
class RedisTestcontainersIntegrationTest(SimpleTestCase):
    def test_rate_limit_state_is_persisted_in_redis(self) -> None:
        with _start_redis_container_or_skip() as container:
            redis_url = f"redis://{container.get_container_host_ip()}:{int(container.get_exposed_port(6379))}/0"
            _wait_for_redis_ready_or_skip(redis_url)

            with override_settings(
                CACHES={
                    "default": {
                        "BACKEND": "django.core.cache.backends.redis.RedisCache",
                        "LOCATION": redis_url,
                    }
                },
            ):
                cache.clear()
                bucket = int(time.time()) // 60
                cache_key = f"{settings.RATE_LIMIT_CACHE_PREFIX}:login:redis-user:{bucket}"

                first_result = check_rate_limit(
                    scope="login",
                    identifier="redis-user",
                    limit=1,
                    window_seconds=60,
                    request_id="redis-request-1",
                )
                second_result = check_rate_limit(
                    scope="login",
                    identifier="redis-user",
                    limit=1,
                    window_seconds=60,
                    request_id="redis-request-2",
                )

                self.assertIsNone(first_result)
                self.assertIsNotNone(second_result)
                self.assertEqual(getattr(second_result, "code", None), "RATE_LIMIT_EXCEEDED")
                self.assertEqual(cache.get(cache_key), 2)

    def test_refresh_token_revocation_uses_redis_backend(self) -> None:
        with _start_redis_container_or_skip() as container:
            redis_url = f"redis://{container.get_container_host_ip()}:{int(container.get_exposed_port(6379))}/0"
            _wait_for_redis_ready_or_skip(redis_url)

            with override_settings(
                CACHES={
                    "default": {
                        "BACKEND": "django.core.cache.backends.redis.RedisCache",
                        "LOCATION": redis_url,
                    }
                },
            ):
                cache.clear()
                refresh_token = _build_refresh_token_payload(42)

                self.assertFalse(refresh_token_is_revoked(refresh_token))
                self.assertFalse(refresh_token_revoked_by_user(refresh_token))

                revoke_refresh_token(refresh_token)
                revoke_user_refresh_tokens(42)

                self.assertTrue(refresh_token_is_revoked(refresh_token))
                self.assertTrue(refresh_token_revoked_by_user(refresh_token))
                self.assertEqual(
                    cache.get(f"{settings.RATE_LIMIT_CACHE_PREFIX}:revoked-refresh:redis-test-jti"),
                    1,
                )
                self.assertIsNotNone(
                    cache.get(f"{settings.RATE_LIMIT_CACHE_PREFIX}:revoked-refresh-before:42"),
                )
