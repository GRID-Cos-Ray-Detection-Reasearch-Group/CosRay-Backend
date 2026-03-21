"""
输入参数与协议一致性校验
"""

import re
from collections.abc import Sequence
from typing import Protocol

from .schemas import ErrorResponse
from .schemas import PacketUpload

_MAC_PATTERN = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")
_UINT8_MAX = 255
_UINT16_MAX = 65535
_UINT32_MAX = 4294967295
_UINT64_MAX = 18446744073709551615
_INT8_MIN = -128
_INT8_MAX = 127
_INT16_MIN = -32768
_INT16_MAX = 32767
_INT32_MIN = -2147483648
_INT32_MAX = 2147483647
_MUON_HEAD = [0xAA, 0xBB, 0xCC]
_MUON_TAIL = [0xDD, 0xEE, 0xFF]
_TIMELINE_HEAD = [0x12, 0x34, 0x56]
_TIMELINE_TAIL = [0x78, 0x9A, 0xBC]


class _MuonEventLike(Protocol):
    cpu_time: int
    energy: int
    pps: int
    timestamp: int | None


class _TimelineEventLike(Protocol):
    cpu_time: int
    pps: int
    utc: int
    pps_utc: int
    cputime_pps: int
    gps_long: int
    gps_lat: int
    gps_alt: int
    acc_x: int
    acc_y: int
    acc_z: int
    sipm_tmp: int
    mcu_tmp: int
    sipm_imon: int
    sipm_vmon: int
    timestamp: int | None


def normalize_mac_or_error(raw_mac: str, request_id: str) -> tuple[str | None, ErrorResponse | None]:
    """规范化 MAC 地址并进行格式校验"""
    normalized_mac = raw_mac.strip().upper()
    if not _MAC_PATTERN.fullmatch(normalized_mac):
        return None, ErrorResponse(
            detail="MAC 地址格式必须为 AA:BB:CC:DD:EE:FF",
            code="INVALID_MAC",
            request_id=request_id,
        )
    return normalized_mac, None


def validate_packet_payload(payload: PacketUpload, request_id: str) -> ErrorResponse | None:
    """校验 packet_type 与包体及包头尾约束"""
    if payload.packet_type not in {"muon", "timeline"}:
        return ErrorResponse(
            detail="packet_type 不受支持",
            code="INVALID_PACKET_TYPE",
            request_id=request_id,
        )
    if payload.packet_type == "muon":
        return _validate_muon_payload(payload, request_id)

    return _validate_timeline_payload(payload, request_id)


def _validate_muon_payload(payload: PacketUpload, request_id: str) -> ErrorResponse | None:
    packet = payload.muon_packet
    if packet is None:
        return ErrorResponse(
            detail="packet_type 为 muon 时必须提供 muon_packet",
            code="MISSING_PAYLOAD",
            request_id=request_id,
        )
    if (
        error := _validate_uint_range(
            packet.package_counter,
            0,
            _UINT32_MAX,
            "muon_packet.package_counter 超出 uint32 范围",
            request_id,
        )
    ) is not None:
        return error
    if (
        error := _validate_uint_range(
            packet.utc,
            0,
            _UINT32_MAX,
            "muon_packet.utc 超出 uint32 范围",
            request_id,
        )
    ) is not None:
        return error
    if len(packet.events) > 35:
        return ErrorResponse(
            detail="muon_packet.events 不能超过 35 个",
            code="MUON_EVENTS_OVER_LIMIT",
            request_id=request_id,
        )
    if (
        error := _validate_expected_sequence(
            packet.head,
            _MUON_HEAD,
            "muon_packet.head 不符合协议约定",
            "INVALID_MUON_HEAD",
            request_id,
        )
    ) is not None:
        return error
    if (
        error := _validate_expected_sequence(
            packet.tail,
            _MUON_TAIL,
            "muon_packet.tail 不符合协议约定",
            "INVALID_MUON_TAIL",
            request_id,
        )
    ) is not None:
        return error
    return _validate_muon_events(packet.events, request_id)


def _validate_timeline_payload(payload: PacketUpload, request_id: str) -> ErrorResponse | None:
    packet = payload.timeline_packet
    if packet is None:
        return ErrorResponse(
            detail="packet_type 为 timeline 时必须提供 timeline_packet",
            code="MISSING_PAYLOAD",
            request_id=request_id,
        )
    if (
        error := _validate_uint_range(
            packet.package_counter,
            0,
            _UINT32_MAX,
            "timeline_packet.package_counter 超出 uint32 范围",
            request_id,
        )
    ) is not None:
        return error
    if len(packet.events) > 10:
        return ErrorResponse(
            detail="timeline_packet.events 不能超过 10 个",
            code="TIMELINE_EVENTS_OVER_LIMIT",
            request_id=request_id,
        )
    if (
        error := _validate_expected_sequence(
            packet.head,
            _TIMELINE_HEAD,
            "timeline_packet.head 不符合协议约定",
            "INVALID_TIMELINE_HEAD",
            request_id,
        )
    ) is not None:
        return error
    if (
        error := _validate_expected_sequence(
            packet.tail,
            _TIMELINE_TAIL,
            "timeline_packet.tail 不符合协议约定",
            "INVALID_TIMELINE_TAIL",
            request_id,
        )
    ) is not None:
        return error
    return _validate_timeline_events(packet.events, request_id)


def _validate_muon_events(events: Sequence[_MuonEventLike], request_id: str) -> ErrorResponse | None:
    for event in events:
        checks = [
            (event.cpu_time, 0, _UINT64_MAX, "muon_packet.events.cpu_time 超出 uint64 范围"),
            (event.energy, 0, _UINT16_MAX, "muon_packet.events.energy 超出 uint16 范围"),
            (event.pps, 0, _UINT32_MAX, "muon_packet.events.pps 超出 uint32 范围"),
        ]
        if event.timestamp is not None:
            checks.append((event.timestamp, 0, _UINT64_MAX, "muon_packet.events.timestamp 超出 uint64 范围"))
        if (error := _validate_range_checks(checks, request_id)) is not None:
            return error
    return None


def _validate_timeline_events(events: Sequence[_TimelineEventLike], request_id: str) -> ErrorResponse | None:
    for event in events:
        checks = [
            (event.cpu_time, 0, _UINT64_MAX, "timeline_packet.events.cpu_time 超出 uint64 范围"),
            (event.pps, 0, _UINT32_MAX, "timeline_packet.events.pps 超出 uint32 范围"),
            (event.utc, 0, _UINT32_MAX, "timeline_packet.events.utc 超出 uint32 范围"),
            (event.pps_utc, 0, _UINT32_MAX, "timeline_packet.events.pps_utc 超出 uint32 范围"),
            (event.cputime_pps, 0, _UINT64_MAX, "timeline_packet.events.cputime_pps 超出 uint64 范围"),
            (event.gps_long, _INT32_MIN, _INT32_MAX, "timeline_packet.events.gps_long 超出 int32 范围"),
            (event.gps_lat, _INT32_MIN, _INT32_MAX, "timeline_packet.events.gps_lat 超出 int32 范围"),
            (event.gps_alt, _INT16_MIN, _INT16_MAX, "timeline_packet.events.gps_alt 超出 int16 范围"),
            (event.acc_x, _INT8_MIN, _INT8_MAX, "timeline_packet.events.acc_x 超出 int8 范围"),
            (event.acc_y, _INT8_MIN, _INT8_MAX, "timeline_packet.events.acc_y 超出 int8 范围"),
            (event.acc_z, _INT8_MIN, _INT8_MAX, "timeline_packet.events.acc_z 超出 int8 范围"),
            (event.sipm_tmp, 0, _UINT16_MAX, "timeline_packet.events.sipm_tmp 超出 uint16 范围"),
            (event.mcu_tmp, 0, _UINT8_MAX, "timeline_packet.events.mcu_tmp 超出 uint8 范围"),
            (event.sipm_imon, 0, _UINT16_MAX, "timeline_packet.events.sipm_imon 超出 uint16 范围"),
            (event.sipm_vmon, 0, _UINT16_MAX, "timeline_packet.events.sipm_vmon 超出 uint16 范围"),
        ]
        if event.timestamp is not None:
            checks.append((event.timestamp, 0, _UINT64_MAX, "timeline_packet.events.timestamp 超出 uint64 范围"))
        if (error := _validate_range_checks(checks, request_id)) is not None:
            return error
    return None


def _validate_expected_sequence(
    actual: Sequence[int] | None,
    expected: Sequence[int],
    detail: str,
    code: str,
    request_id: str,
) -> ErrorResponse | None:
    if actual is not None and actual != expected:
        return ErrorResponse(detail=detail, code=code, request_id=request_id)
    return None


def _validate_uint_range(value: int, minimum: int, maximum: int, detail: str, request_id: str) -> ErrorResponse | None:
    return _validate_range_checks([(value, minimum, maximum, detail)], request_id)


def _validate_range_checks(
    checks: Sequence[tuple[int, int, int, str]],
    request_id: str,
) -> ErrorResponse | None:
    for value, minimum, maximum, detail in checks:
        if not minimum <= value <= maximum:
            return _invalid_payload(detail, request_id)
    return None


def _invalid_payload(detail: str, request_id: str) -> ErrorResponse:
    return ErrorResponse(detail=detail, code="INVALID_PAYLOAD", request_id=request_id)
