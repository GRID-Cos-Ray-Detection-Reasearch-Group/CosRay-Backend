import json
from contextlib import AbstractContextManager
from contextlib import nullcontext
from pathlib import Path
from typing import Any
from typing import NotRequired
from typing import TypedDict
from typing import cast
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.test import TestCase
from pydantic import ValidationError

from core.api import upload_packet
from core.models import Detector
from core.schemas import PacketUpload


class _FixtureExpected(TypedDict):
    status_code: int
    code: str | None


class _PacketFixture(TypedDict):
    request: dict[str, Any]
    expected: _FixtureExpected
    as_user: NotRequired[str]
    patch: NotRequired[dict[str, Any]]


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
        fixture_paths = self._load_fixture_paths()
        self.assertGreaterEqual(len(fixture_paths), 8)

        invalid_fixture_count = 0

        for fixture_path in fixture_paths:
            if self._fixture_is_invalid(fixture_path):
                invalid_fixture_count += 1
            with self.subTest(fixture=fixture_path.name):
                self._assert_fixture_contract(fixture_path)

        self.assertGreaterEqual(invalid_fixture_count, 8)

    def _load_fixture_paths(self) -> list[Path]:
        fixtures_dir = Path(__file__).resolve().parent / "fixtures" / "packet_upload"
        return sorted(fixtures_dir.glob("*.json"))

    def _fixture_is_invalid(self, fixture_path: Path) -> bool:
        fixture: _PacketFixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        status_code: int = fixture["expected"]["status_code"]
        return status_code != 200

    def _assert_fixture_contract(self, fixture_path: Path) -> None:
        fixture: _PacketFixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        user = self.owner if fixture.get("as_user") == "owner" else self.other
        request = self._request_with_user(user)

        expected = fixture["expected"]
        if expected.get("code") == "INVALID_PACKET_TYPE":
            with pytest.raises(ValidationError):
                PacketUpload(**fixture["request"])
            return

        try:
            payload = PacketUpload(**fixture["request"])
        except ValidationError as exc:
            message = f"Invalid contract fixture request payload: {fixture_path.name}"
            raise AssertionError(message) from exc

        with self._build_patch_context(fixture.get("patch")):
            result = upload_packet(request, payload)

        status_code, response = self._normalize_result(result)
        self.assertEqual(status_code, expected["status_code"])
        self.assert_is_valid_response_id(response)
        self._assert_expected_response_fields(response, expected)

    def _build_patch_context(self, patch_spec: dict[str, Any] | None) -> AbstractContextManager[Any]:
        if patch_spec is None:
            return nullcontext()

        target = patch_spec["target"]
        patch_kwargs: dict[str, Any] = {}
        if "return_value" in patch_spec:
            patch_kwargs["return_value"] = patch_spec["return_value"]
        if "side_effect" in patch_spec:
            patch_kwargs["side_effect"] = patch_spec["side_effect"]
        return cast("AbstractContextManager[Any]", patch(target, **patch_kwargs))

    def _normalize_result(self, result: Any) -> tuple[int, Any]:
        if isinstance(result, tuple):
            return result[0], result[1]
        return 200, result

    def assert_is_valid_response_id(self, response: Any) -> None:
        self.assertIsInstance(getattr(response, "request_id", None), str)
        self.assertTrue(getattr(response, "request_id", "").strip())

    def _assert_expected_response_fields(self, response: Any, expected: _FixtureExpected) -> None:
        expected_code = expected.get("code")
        if expected_code is not None:
            self.assertEqual(getattr(response, "code", None), expected_code)

        expected_records_written = expected.get("records_written")
        if expected_records_written is not None:
            self.assertEqual(getattr(response, "records_written", None), expected_records_written)
