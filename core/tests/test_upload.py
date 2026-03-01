import typing
from unittest.mock import MagicMock
from unittest.mock import patch

from django.contrib.auth.models import User
from django.http import HttpRequest
from django.test import Client
from django.test import TestCase

from core.api import create_device
from core.api import upload_packet
from core.models import Detector
from core.schemas import DetectorCreate
from core.schemas import MuonEvent
from core.schemas import MuonPacket
from core.schemas import PacketUpload
from core.schemas import TimelineEvent
from core.schemas import TimelinePacket


class UploadValidationTest(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="u1", password="pass1234")
        self.other_user = User.objects.create_user(username="u2", password="pass1234")
        self.detector = Detector.objects.create(
            mac_address="AA:BB:CC:DD:EE:FF",
            name="D1",
            owner=self.user,
            description="",
        )

    def _request_with_user(self, user: User) -> HttpRequest:
        request = HttpRequest()
        request.user = user
        return request

    def test_create_device_invalid_mac_returns_400(self) -> None:
        request = self._request_with_user(self.user)
        status_code, response = create_device(
            request,
            DetectorCreate(mac_address="invalid", name="bad", description=None),
        )

        self.assertEqual(status_code, 400)
        self.assertEqual(getattr(response, "code", None), "INVALID_MAC_ADDRESS")

    def test_create_device_duplicate_mac_returns_400(self) -> None:
        request = self._request_with_user(self.user)
        status_code, response = create_device(
            request,
            DetectorCreate(mac_address="aa:bb:cc:dd:ee:ff", name="dup", description=None),
        )

        self.assertEqual(status_code, 400)
        self.assertEqual(getattr(response, "code", None), "DEVICE_EXISTS")

    def test_upload_packet_non_owned_device_returns_404(self) -> None:
        request = self._request_with_user(self.other_user)
        payload = PacketUpload(
            device="AA:BB:CC:DD:EE:FF",
            packet_type="muon",
            muon_packet=MuonPacket(package_counter=1, utc=1, events=[MuonEvent(cpu_time=1, energy=2, pps=3)]),
        )

        status_code, response = upload_packet(request, payload)

        self.assertEqual(status_code, 404)
        self.assertEqual(getattr(response, "code", None), "DEVICE_NOT_FOUND")

    def test_upload_packet_invalid_muon_head_returns_400(self) -> None:
        request = self._request_with_user(self.user)
        payload = PacketUpload(
            device="AA:BB:CC:DD:EE:FF",
            packet_type="muon",
            muon_packet=MuonPacket(
                package_counter=1,
                utc=1,
                events=[MuonEvent(cpu_time=1, energy=2, pps=3)],
                head=[0, 0, 0],
            ),
        )

        status_code, response = upload_packet(request, payload)

        self.assertEqual(status_code, 400)
        self.assertEqual(getattr(response, "code", None), "INVALID_MUON_HEAD")

    def test_upload_packet_missing_muon_packet_returns_invalid_packet(self) -> None:
        request = self._request_with_user(self.user)
        payload = PacketUpload(
            device="AA:BB:CC:DD:EE:FF",
            packet_type="muon",
        )

        status_code, response = upload_packet(request, payload)

        self.assertEqual(status_code, 400)
        self.assertEqual(getattr(response, "code", None), "INVALID_PACKET")

    def test_upload_packet_timeline_events_over_limit_returns_400(self) -> None:
        request = self._request_with_user(self.user)
        events = [
            TimelineEvent(
                cpu_time=1,
                pps=1,
                utc=1,
                pps_utc=1,
                cputime_pps=1,
                gps_long=0,
                gps_lat=0,
                gps_alt=0,
                acc_x=0,
                acc_y=0,
                acc_z=0,
                sipm_tmp=1,
                mcu_tmp=1,
                sipm_imon=1,
                sipm_vmon=1,
            )
            for _ in range(11)
        ]
        payload = PacketUpload(
            device="AA:BB:CC:DD:EE:FF",
            packet_type="timeline",
            timeline_packet=TimelinePacket(package_counter=1, events=events),
        )

        status_code, response = upload_packet(request, payload)

        self.assertEqual(status_code, 400)
        self.assertEqual(getattr(response, "code", None), "TIMELINE_EVENTS_OVER_LIMIT")

    def test_upload_packet_timeline_invalid_head_returns_400(self) -> None:
        request = self._request_with_user(self.user)
        payload = PacketUpload(
            device="AA:BB:CC:DD:EE:FF",
            packet_type="timeline",
            timeline_packet=TimelinePacket(
                package_counter=1,
                events=[
                    TimelineEvent(
                        cpu_time=1,
                        pps=1,
                        utc=1,
                        pps_utc=1,
                        cputime_pps=1,
                        gps_long=0,
                        gps_lat=0,
                        gps_alt=0,
                        acc_x=0,
                        acc_y=0,
                        acc_z=0,
                        sipm_tmp=1,
                        mcu_tmp=1,
                        sipm_imon=1,
                        sipm_vmon=1,
                    )
                ],
                head=[1, 2, 3],
            ),
        )

        status_code, response = upload_packet(request, payload)

        self.assertEqual(status_code, 400)
        self.assertEqual(getattr(response, "code", None), "INVALID_TIMELINE_HEAD")

    def test_upload_packet_missing_timeline_packet_returns_invalid_packet(self) -> None:
        request = self._request_with_user(self.user)
        payload = PacketUpload(
            device="AA:BB:CC:DD:EE:FF",
            packet_type="timeline",
        )

        status_code, response = upload_packet(request, payload)

        self.assertEqual(status_code, 400)
        self.assertEqual(getattr(response, "code", None), "INVALID_PACKET")

    def test_upload_packet_invalid_mac_returns_400(self) -> None:
        request = self._request_with_user(self.user)
        payload = PacketUpload(device="bad-mac", packet_type="muon")

        status_code, response = upload_packet(request, payload)

        self.assertEqual(status_code, 400)
        self.assertEqual(getattr(response, "code", None), "INVALID_MAC_ADDRESS")

    @patch("core.api.ingest_muon_packet", side_effect=RuntimeError("iotdb failed"))
    def test_upload_packet_iotdb_error_returns_400(self, mock_ingest: MagicMock) -> None:
        request = self._request_with_user(self.user)
        payload = PacketUpload(
            device="AA:BB:CC:DD:EE:FF",
            packet_type="muon",
            muon_packet=MuonPacket(package_counter=1, utc=1, events=[MuonEvent(cpu_time=1, energy=2, pps=3)]),
        )

        status_code, response = upload_packet(request, payload)

        self.assertEqual(status_code, 400)
        self.assertEqual(getattr(response, "code", None), "IOTDB_WRITE_ERROR")
        mock_ingest.assert_called_once()

    @patch("core.api.ingest_muon_packet", return_value=1)
    def test_upload_packet_success_updates_last_seen(self, mock_ingest: MagicMock) -> None:
        request = self._request_with_user(self.user)
        payload = PacketUpload(
            device="AA:BB:CC:DD:EE:FF",
            packet_type="muon",
            muon_packet=MuonPacket(
                package_counter=1,
                utc=1,
                events=[MuonEvent(cpu_time=1, energy=2, pps=3)],
                head=[0xAA, 0xBB, 0xCC],
                tail=[0xDD, 0xEE, 0xFF],
            ),
        )

        response = upload_packet(request, payload)

        self.assertEqual(getattr(response, "records_written", None), 1)
        self.assertEqual(getattr(response, "device", None), "AA:BB:CC:DD:EE:FF")
        self.assertEqual(getattr(response, "device_name", None), "D1")
        self.detector.refresh_from_db()
        self.assertIsNotNone(self.detector.last_seen_at)
        mock_ingest.assert_called_once()


class UploadHttpIntegrationTest(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.username = "http_upload_user"
        self.password = "Pass1234!"
        self.user = User.objects.create_user(username=self.username, password=self.password, email="u@example.com")

        pair_response = self.client.post(
            "/api/token/pair",
            data={"username": self.username, "password": self.password},
            content_type="application/json",
        )
        self.assertEqual(pair_response.status_code, 200)
        self.access_token = pair_response.json()["access"]

    def _auth_header(self) -> dict[str, typing.Any]:
        return {"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"}

    @patch("core.api.ingest_timeline_packet", return_value=1)
    def test_upload_timeline_success_path(self, mock_ingest: MagicMock) -> None:
        Detector.objects.create(
            mac_address="22:33:44:55:66:77",
            name="TimelineDevice",
            owner=self.user,
            description="",
        )

        payload = {
            "device": "22:33:44:55:66:77",
            "packet_type": "timeline",
            "timeline_packet": {
                "package_counter": 1,
                "head": [0x12, 0x34, 0x56],
                "tail": [0x78, 0x9A, 0xBC],
                "events": [
                    {
                        "cpu_time": 1,
                        "pps": 1,
                        "utc": 1,
                        "pps_utc": 1,
                        "cputime_pps": 1,
                        "gps_long": 0,
                        "gps_lat": 0,
                        "gps_alt": 0,
                        "acc_x": 0,
                        "acc_y": 0,
                        "acc_z": 0,
                        "sipm_tmp": 1,
                        "mcu_tmp": 1,
                        "sipm_imon": 1,
                        "sipm_vmon": 1,
                    }
                ],
            },
        }

        response = self.client.post(
            "/api/mu-packets/",
            data=payload,
            content_type="application/json",
            **self._auth_header(),
        )

        self.assertEqual(response.status_code, 200)
        response_payload = response.json()
        self.assertEqual(response_payload["records_written"], 1)
        self.assertEqual(response_payload["device"], "22:33:44:55:66:77")
        self.assertEqual(response_payload["device_name"], "TimelineDevice")
        self.assertEqual(response_payload["packet_type"], "timeline")
        mock_ingest.assert_called_once()
