from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client
from django.test import TestCase
from django.test import override_settings


class AuthEndpointTest(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.username = "auth_user"
        self.password = "Pass1234!"
        User.objects.create_user(username=self.username, password=self.password)
        cache.clear()

    def test_token_pair_and_refresh_endpoint_available(self) -> None:
        pair_response = self.client.post(
            "/api/token/pair",
            data={"username": self.username, "password": self.password},
            content_type="application/json",
        )
        self.assertEqual(pair_response.status_code, 200)
        pair_payload = pair_response.json()
        self.assertIn("access", pair_payload)
        self.assertIn("refresh", pair_payload)

        refresh_response = self.client.post(
            "/api/token/refresh",
            data={"refresh": pair_payload["refresh"]},
            content_type="application/json",
        )
        self.assertEqual(refresh_response.status_code, 200)
        refresh_payload = refresh_response.json()
        self.assertIn("access", refresh_payload)
        self.assertIn("refresh", refresh_payload)

    def test_refresh_token_cannot_be_reused_after_rotation(self) -> None:
        pair_response = self.client.post(
            "/api/token/pair",
            data={"username": self.username, "password": self.password},
            content_type="application/json",
        )
        self.assertEqual(pair_response.status_code, 200)
        refresh_token = pair_response.json()["refresh"]

        first_refresh = self.client.post(
            "/api/token/refresh",
            data={"refresh": refresh_token},
            content_type="application/json",
        )
        self.assertEqual(first_refresh.status_code, 200)

        second_refresh = self.client.post(
            "/api/token/refresh",
            data={"refresh": refresh_token},
            content_type="application/json",
        )
        self.assertEqual(second_refresh.status_code, 401)
        self.assertEqual(second_refresh.json()["code"], "INVALID_TOKEN")

    def test_register_endpoint_create_user_and_return_tokens(self) -> None:
        response = self.client.post(
            "/api/auth/register",
            data={"username": "new_user", "email": "new_user@example.com", "password": "Pass1234!"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("access", payload)
        self.assertIn("refresh", payload)
        self.assertIn("user", payload)
        self.assertEqual(payload["user"]["username"], "new_user")
        self.assertEqual(payload["user"]["email"], "new_user@example.com")
        self.assertTrue(User.objects.filter(username="new_user").exists())

    def test_register_endpoint_with_duplicate_username_return_409(self) -> None:
        response = self.client.post(
            "/api/auth/register",
            data={"username": self.username, "email": "duplicate@example.com", "password": "Pass1234!"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "注册信息不可用")

    def test_login_with_invalid_password_returns_generic_error(self) -> None:
        response = self.client.post(
            "/api/token/pair",
            data={"username": self.username, "password": "wrong-password"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "用户名或密码错误")
        self.assertEqual(response.json()["code"], "INVALID_CREDENTIALS")

    @override_settings(LOGIN_RATE_LIMIT_COUNT=1, LOGIN_RATE_LIMIT_WINDOW_SECONDS=60)
    def test_login_rate_limit_returns_429(self) -> None:
        cache.clear()

        first_response = self.client.post(
            "/api/token/pair",
            data={"username": self.username, "password": "wrong-password"},
            content_type="application/json",
        )
        second_response = self.client.post(
            "/api/token/pair",
            data={"username": self.username, "password": "wrong-password"},
            content_type="application/json",
        )

        self.assertEqual(first_response.status_code, 401)
        self.assertEqual(second_response.status_code, 429)
        self.assertEqual(second_response.json()["code"], "RATE_LIMIT_EXCEEDED")

    @override_settings(REGISTER_RATE_LIMIT_COUNT=1, REGISTER_RATE_LIMIT_WINDOW_SECONDS=60)
    def test_register_rate_limit_returns_429(self) -> None:
        cache.clear()

        first_response = self.client.post(
            "/api/auth/register",
            data={"username": "first_user", "email": "first@example.com", "password": "Pass1234!"},
            content_type="application/json",
        )
        second_response = self.client.post(
            "/api/auth/register",
            data={"username": "second_user", "email": "second@example.com", "password": "Pass1234!"},
            content_type="application/json",
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 429)
        self.assertEqual(second_response.json()["detail"], "请求过于频繁, 请稍后再试")


class SecuritySettingsTest(TestCase):
    def test_jwt_settings_are_hardened(self) -> None:
        self.assertTrue(settings.NINJA_JWT["ROTATE_REFRESH_TOKENS"])
        self.assertTrue(settings.NINJA_JWT["BLACKLIST_AFTER_ROTATION"])
        self.assertFalse(settings.NINJA_JWT["UPDATE_LAST_LOGIN"])

    def test_production_security_settings_are_defined(self) -> None:
        self.assertTrue(hasattr(settings, "SECURE_SSL_REDIRECT"))
        self.assertTrue(hasattr(settings, "SESSION_COOKIE_SECURE"))
        self.assertTrue(hasattr(settings, "CSRF_COOKIE_SECURE"))
