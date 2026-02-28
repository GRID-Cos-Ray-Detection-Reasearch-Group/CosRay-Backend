from django.contrib.auth.models import User
from django.test import Client
from django.test import TestCase


class AuthEndpointTest(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.username = "auth_user"
        self.password = "Pass1234!"
        User.objects.create_user(username=self.username, password=self.password)

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
