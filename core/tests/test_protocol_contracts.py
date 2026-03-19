import json
from contextlib import nullcontext
from pathlib import Path
from typing import Any
from unittest.mock import patch

from django.contrib.auth.models import User
from django.http import HttpRequest
from django.test import TestCase

from core.api import upload_packet
from core.models import Detector
from core.schemas import PacketUpload


class PacketUploadContractTest(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="owner", password="pass1234")
        self.other = User.objects.create_user(username="other", password="pass1234")
        Detector.objects.create(
            mac_address="AA:BB:CC:DD:EE:FF",
            name="D1",
            owner=self.owner,
            description="",
        )

    def _request_with_user(self, user: User) -> HttpRequest:
        request = HttpRequest()
        request.user = user
        return request

    def test_packet_upload_golden_contracts(self) -> None:
        fixtures_dir = Path(__file__).resolve().parent / "fixtures" / "packet_upload"
        fixture_paths = sorted(fixtures_dir.glob("*.json"))
        self.assertGreaterEqual(len(fixture_paths), 6)

        for fixture_path in fixture_paths:
            with self.subTest(fixture=fixture_path.name):
                fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
                as_user = fixture.get("as_user")
                user = self.owner if as_user == "owner" else self.other
                request = self._request_with_user(user)
                payload = PacketUpload(**fixture["request"])

                patch_spec = fixture.get("patch")
                if patch_spec is None:
                    patch_context = nullcontext()
                else:
                    target = patch_spec["target"]
                    patch_kwargs: dict[str, Any] = {}
                    if "return_value" in patch_spec:
                        patch_kwargs["return_value"] = patch_spec["return_value"]
                    if "side_effect" in patch_spec:
                        patch_kwargs["side_effect"] = patch_spec["side_effect"]
                    patch_context = patch(target, **patch_kwargs)

                with patch_context:
                    result = upload_packet(request, payload)

                if isinstance(result, tuple):
                    status_code = result[0]
                    response: Any = result[1]
                else:
                    status_code = 200
                    response = result

                expected = fixture["expected"]
                self.assertEqual(status_code, expected["status_code"])
                self.assertIsInstance(getattr(response, "request_id", None), str)
                self.assertTrue(getattr(response, "request_id", "").strip())

                expected_code = expected.get("code")
                if expected_code is not None:
                    self.assertEqual(getattr(response, "code", None), expected_code)

                expected_records_written = expected.get("records_written")
                if expected_records_written is not None:
                    self.assertEqual(getattr(response, "records_written", None), expected_records_written)
