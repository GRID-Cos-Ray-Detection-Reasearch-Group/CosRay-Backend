"""
输入参数与协议一致性校验
"""

import re

from .schemas import ErrorResponse
from .schemas import PacketUpload

_MAC_PATTERN = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")
_MUON_HEAD = [0xAA, 0xBB, 0xCC]
_MUON_TAIL = [0xDD, 0xEE, 0xFF]
_TIMELINE_HEAD = [0x12, 0x34, 0x56]
_TIMELINE_TAIL = [0x78, 0x9A, 0xBC]


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
    if payload.muon_packet is None:
        return ErrorResponse(
            detail="packet_type 为 muon 时必须提供 muon_packet",
            code="MISSING_PAYLOAD",
            request_id=request_id,
        )
    if len(payload.muon_packet.events) > 35:
        return ErrorResponse(
            detail="muon_packet.events 不能超过 35 个",
            code="MUON_EVENTS_OVER_LIMIT",
            request_id=request_id,
        )
    if payload.muon_packet.head is not None and payload.muon_packet.head != _MUON_HEAD:
        return ErrorResponse(
            detail="muon_packet.head 不符合协议约定",
            code="INVALID_MUON_HEAD",
            request_id=request_id,
        )
    if payload.muon_packet.tail is not None and payload.muon_packet.tail != _MUON_TAIL:
        return ErrorResponse(
            detail="muon_packet.tail 不符合协议约定",
            code="INVALID_MUON_TAIL",
            request_id=request_id,
        )
    return None


def _validate_timeline_payload(payload: PacketUpload, request_id: str) -> ErrorResponse | None:
    if payload.timeline_packet is None:
        return ErrorResponse(
            detail="packet_type 为 timeline 时必须提供 timeline_packet",
            code="MISSING_PAYLOAD",
            request_id=request_id,
        )
    if len(payload.timeline_packet.events) > 10:
        return ErrorResponse(
            detail="timeline_packet.events 不能超过 10 个",
            code="TIMELINE_EVENTS_OVER_LIMIT",
            request_id=request_id,
        )
    if payload.timeline_packet.head is not None and payload.timeline_packet.head != _TIMELINE_HEAD:
        return ErrorResponse(
            detail="timeline_packet.head 不符合协议约定",
            code="INVALID_TIMELINE_HEAD",
            request_id=request_id,
        )
    if payload.timeline_packet.tail is not None and payload.timeline_packet.tail != _TIMELINE_TAIL:
        return ErrorResponse(
            detail="timeline_packet.tail 不符合协议约定",
            code="INVALID_TIMELINE_TAIL",
            request_id=request_id,
        )
    return None
