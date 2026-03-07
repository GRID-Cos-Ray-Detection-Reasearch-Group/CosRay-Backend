import typing

from django.contrib.auth.models import User
from django.test import Client
from django.test import TestCase

from core.models import Detector


class DevicesHttpIntegrationTest(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.username = "http_user"
        self.password = "Pass1234!"
        self.user = User.objects.create_user(username=self.username, password=self.password, email="u@example.com")
        self.other_user = User.objects.create_user(
            username="other_http_user",
            password="Pass1234!",
            email="other@example.com",
        )

        pair_response = self.client.post(
            "/api/token/pair",
            data={"username": self.username, "password": self.password},
            content_type="application/json",
        )
        self.assertEqual(pair_response.status_code, 200)
        self.access_token = pair_response.json()["access"]

        other_pair_response = self.client.post(
            "/api/token/pair",
            data={"username": "other_http_user", "password": "Pass1234!"},
            content_type="application/json",
        )
        self.assertEqual(other_pair_response.status_code, 200)
        self.other_access_token = other_pair_response.json()["access"]

    def _auth_header(self) -> dict[str, typing.Any]:
        return {"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"}

    def _other_auth_header(self) -> dict[str, typing.Any]:
        return {"HTTP_AUTHORIZATION": f"Bearer {self.other_access_token}"}

    def test_protected_endpoints_require_authentication(self) -> None:
        users_me_response = self.client.get("/api/users/me")
        self.assertEqual(users_me_response.status_code, 401)

        devices_response = self.client.get("/api/devices/")
        self.assertEqual(devices_response.status_code, 401)

    def test_users_me_returns_authenticated_user(self) -> None:
        response = self.client.get("/api/users/me", **self._auth_header())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["username"], self.username)
        self.assertEqual(payload["email"], "u@example.com")

    def test_devices_crud_flow(self) -> None:
        create_response = self.client.post(
            "/api/devices/",
            data={
                "mac_address": "11:22:33:44:55:66",
                "name": "Detector-1",
                "description": "desc",
            },
            content_type="application/json",
            **self._auth_header(),
        )
        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        device_id = created["id"]

        list_response = self.client.get("/api/devices/", **self._auth_header())
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()), 1)

        detail_response = self.client.get(f"/api/devices/{device_id}/", **self._auth_header())
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["mac_address"], "11:22:33:44:55:66")

        update_response = self.client.patch(
            f"/api/devices/{device_id}/",
            data={"name": "Detector-1-updated", "is_active": False},
            content_type="application/json",
            **self._auth_header(),
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["name"], "Detector-1-updated")
        self.assertFalse(update_response.json()["is_active"])

        delete_response = self.client.delete(f"/api/devices/{device_id}/", **self._auth_header())
        self.assertEqual(delete_response.status_code, 204)

        list_after_delete = self.client.get("/api/devices/", **self._auth_header())
        self.assertEqual(list_after_delete.status_code, 200)
        self.assertEqual(len(list_after_delete.json()), 0)

    def test_cross_user_device_access_returns_404(self) -> None:
        detector = Detector.objects.create(
            mac_address="AA:BB:CC:DD:EE:11",
            name="OwnedByPrimary",
            owner=self.user,
            description="",
        )

        detail_response = self.client.get(f"/api/devices/{detector.id}/", **self._other_auth_header())
        self.assertEqual(detail_response.status_code, 404)

        update_response = self.client.patch(
            f"/api/devices/{detector.id}/",
            data={"name": "Hacked"},
            content_type="application/json",
            **self._other_auth_header(),
        )
        self.assertEqual(update_response.status_code, 404)

        delete_response = self.client.delete(f"/api/devices/{detector.id}/", **self._other_auth_header())
        self.assertEqual(delete_response.status_code, 404)

        detector.refresh_from_db()
        self.assertEqual(detector.name, "OwnedByPrimary")
