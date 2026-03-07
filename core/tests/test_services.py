from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.test import SimpleTestCase

from core.schemas import MuonEvent
from core.schemas import MuonPacket
from core.schemas import TimelineEvent
from core.schemas import TimelinePacket
from core.services import IoTDBWriteError
from core.services import ingest_muon_packet
from core.services import ingest_timeline_packet
from core.services import normalize_device_path


class IoTDBPathTest(SimpleTestCase):
    def test_normalize_device_path_with_packet_type(self) -> None:
        path = normalize_device_path("aa:bb:cc:dd:ee:ff", "muon")

        self.assertEqual(path, "root.cosray.AA_BB_CC_DD_EE_FF.muon")

    @patch("core.services.get_iotdb_pool")
    def test_ingest_muon_packet_writes_to_muon_path(self, mock_get_pool: MagicMock) -> None:
        mock_session = MagicMock()
        mock_pool = MagicMock()
        mock_pool.get_session.return_value = mock_session
        mock_get_pool.return_value = mock_pool

        packet = MuonPacket(
            package_counter=1,
            utc=1710000000,
            events=[MuonEvent(cpu_time=100, energy=200, pps=300)],
        )

        written = ingest_muon_packet("AA:BB:CC:DD:EE:FF", packet)

        self.assertEqual(written, 1)
        call_args = mock_session.insert_records.call_args.args
        self.assertEqual(call_args[0], ["root.cosray.AA_BB_CC_DD_EE_FF.muon"])
        mock_pool.put_back.assert_called_once_with(mock_session)

    @patch("core.services.get_iotdb_pool")
    def test_ingest_timeline_packet_writes_to_timeline_path(self, mock_get_pool: MagicMock) -> None:
        mock_session = MagicMock()
        mock_pool = MagicMock()
        mock_pool.get_session.return_value = mock_session
        mock_get_pool.return_value = mock_pool

        packet = TimelinePacket(
            package_counter=1,
            events=[
                TimelineEvent(
                    cpu_time=1,
                    pps=1,
                    utc=1710000000,
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
        )

        written = ingest_timeline_packet("AA:BB:CC:DD:EE:FF", packet)

        self.assertEqual(written, 1)
        call_args = mock_session.insert_records.call_args.args
        self.assertEqual(call_args[0], ["root.cosray.AA_BB_CC_DD_EE_FF.timeline"])
        mock_pool.put_back.assert_called_once_with(mock_session)

    def test_normalize_device_path_without_packet_type(self) -> None:
        path = normalize_device_path("aa:bb:cc:dd:ee:ff")
        self.assertEqual(path, "root.cosray.AA_BB_CC_DD_EE_FF")

    @patch("core.services.get_iotdb_pool")
    def test_ingest_muon_packet_handles_insert_error(self, mock_get_pool: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session.insert_records.side_effect = Exception("insert failed")

        mock_pool = MagicMock()
        mock_pool.get_session.return_value = mock_session
        mock_get_pool.return_value = mock_pool

        packet = MuonPacket(
            package_counter=1,
            utc=1710000000,
            events=[MuonEvent(cpu_time=100, energy=200, pps=300)],
        )

        with pytest.raises(IoTDBWriteError, match="Muon packet write failed"):
            ingest_muon_packet("AA:BB:CC:DD:EE:FF", packet)

        mock_pool.put_back.assert_called_once_with(mock_session)

    @patch("core.services.get_iotdb_pool")
    def test_ingest_timeline_packet_handles_insert_error(self, mock_get_pool: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session.insert_records.side_effect = Exception("insert failed")

        mock_pool = MagicMock()
        mock_pool.get_session.return_value = mock_session
        mock_get_pool.return_value = mock_pool

        packet = TimelinePacket(
            package_counter=1,
            events=[
                TimelineEvent(
                    cpu_time=1,
                    pps=1,
                    utc=1710000000,
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
        )

        with pytest.raises(IoTDBWriteError, match="Timeline packet write failed"):
            ingest_timeline_packet("AA:BB:CC:DD:EE:FF", packet)

        mock_pool.put_back.assert_called_once_with(mock_session)

    @patch("core.services.get_iotdb_pool")
    def test_ingest_muon_packet_with_empty_events_returns_zero(self, mock_get_pool: MagicMock) -> None:
        packet = MuonPacket(package_counter=1, utc=1710000000, events=[])

        written = ingest_muon_packet("AA:BB:CC:DD:EE:FF", packet)

        self.assertEqual(written, 0)
        mock_get_pool.assert_not_called()

    @patch("core.services.get_iotdb_pool")
    def test_ingest_timeline_packet_with_empty_events_returns_zero(self, mock_get_pool: MagicMock) -> None:
        packet = TimelinePacket(package_counter=1, events=[])

        written = ingest_timeline_packet("AA:BB:CC:DD:EE:FF", packet)

        self.assertEqual(written, 0)
        mock_get_pool.assert_not_called()
