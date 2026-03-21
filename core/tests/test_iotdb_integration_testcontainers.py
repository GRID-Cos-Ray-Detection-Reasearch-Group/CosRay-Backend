import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

import docker
import pytest
from django.test import SimpleTestCase
from docker.errors import APIError
from docker.errors import DockerException
from docker.errors import ImageNotFound
from iotdb.Session import Session
from testcontainers.core.container import DockerContainer

from core.schemas import MuonEvent
from core.schemas import MuonPacket
from core.services import ingest_muon_packet


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
def _start_container_or_skip(image: str) -> Iterator[DockerContainer]:
    try:
        container_ctx = DockerContainer(image).with_exposed_ports(6667)
        container = container_ctx.__enter__()
    except (APIError, DockerException, ImageNotFound, OSError) as exc:
        pytest.skip(f"Testcontainers unavailable in this environment: {exc}")

    try:
        yield container
    finally:
        container_ctx.__exit__(None, None, None)


def _wait_for_iotdb_ready_or_skip(host: str, port: int) -> None:
    deadline = time.monotonic() + 60
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        session = Session(host, port, user="root", password="root")
        try:
            session.open(enable_rpc_compression=False)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(1)
            continue
        try:
            session.execute_non_query_statement("CREATE DATABASE root.cosray")
            session.execute_non_query_statement(
                "CREATE TIMESERIES root.cosray.AA_BB_CC_DD_EE_FF.muon.cpu_time "
                "WITH DATATYPE=INT64, ENCODING=PLAIN, COMPRESSOR=UNCOMPRESSED",
            )
            session.execute_non_query_statement(
                "CREATE TIMESERIES root.cosray.AA_BB_CC_DD_EE_FF.muon.energy "
                "WITH DATATYPE=INT32, ENCODING=PLAIN, COMPRESSOR=UNCOMPRESSED",
            )
            session.execute_non_query_statement(
                "CREATE TIMESERIES root.cosray.AA_BB_CC_DD_EE_FF.muon.pps "
                "WITH DATATYPE=INT64, ENCODING=PLAIN, COMPRESSOR=UNCOMPRESSED",
            )
            return
        finally:
            session.close()

    pytest.skip(f"IoTDB was not ready: {last_error}")


@pytest.mark.skipif(not _can_run_testcontainers(), reason="Testcontainers requires local container runtime")
class IoTDBTestcontainersIntegrationTest(SimpleTestCase):
    def test_ingest_muon_packet_writes_and_is_queryable(self) -> None:
        image = "apache/iotdb:2.0.7-standalone"
        with _start_container_or_skip(image) as container:
            host = container.get_container_host_ip()
            port = int(container.get_exposed_port(6667))

            _wait_for_iotdb_ready_or_skip(host, port)

            with patch("core.services.get_iotdb_pool") as mock_get_pool:
                mock_pool = mock_get_pool.return_value
                ingest_session = Session(host, port, user="root", password="root")
                ingest_session.open(enable_rpc_compression=False)
                mock_pool.get_session.return_value = ingest_session
                mock_pool.put_back.side_effect = lambda s: s.close()

                packet = MuonPacket(
                    package_counter=1,
                    utc=1735689600,
                    events=[MuonEvent(cpu_time=100, energy=42, pps=7, timestamp=1735689600000)],
                )

                written = ingest_muon_packet("AA:BB:CC:DD:EE:FF", packet)
                assert written == 1

                used_session = mock_pool.get_session.return_value
                try:
                    dataset = used_session.execute_query_statement(
                        "SELECT cpu_time, energy, pps FROM root.cosray.AA_BB_CC_DD_EE_FF.muon",
                    )
                    assert dataset.has_next()
                    record = dataset.next()
                    assert record is not None
                    assert record.get_timestamp() == 1735689600000
                    fields = record.get_fields()
                    assert len(fields) == 3
                    assert fields[0].get_long_value() == 100
                    assert fields[1].get_int_value() == 42
                    assert fields[2].get_long_value() == 7
                finally:
                    used_session.close()
