"""
Django Ninja API 路由
"""

import logging
from datetime import UTC
from datetime import datetime

from django.contrib.auth.models import User
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja_jwt.authentication import JWTAuth

from .models import Detector
from .schemas import DetectorCreate
from .schemas import DetectorOut
from .schemas import DetectorUpdate
from .schemas import ErrorResponse
from .schemas import PacketUpload
from .schemas import PacketUploadResponse
from .services import ingest_muon_packet
from .services import ingest_timeline_packet

logger = logging.getLogger(__name__)

# 创建路由器, 默认使用 JWT 认证
router = Router(auth=JWTAuth())


# ============================================================================
# 设备管理 API
# ============================================================================


@router.get("/devices/", response=list[DetectorOut], tags=["Devices"])
def list_devices(request: HttpRequest) -> list[DetectorOut]:
    """获取当前用户的所有设备"""
    user = request.user
    assert isinstance(user, User), "User must be authenticated"
    detectors = Detector.objects.filter(owner=user).select_related("owner")
    return [DetectorOut.from_orm(d) for d in detectors]


@router.post(
    "/devices/",
    response={201: DetectorOut, 400: ErrorResponse},
    tags=["Devices"],
)
def create_device(request: HttpRequest, payload: DetectorCreate) -> tuple[int, DetectorOut | ErrorResponse]:
    """注册新设备"""
    # 检查 MAC 地址是否已存在
    if Detector.objects.filter(mac_address=payload.mac_address.upper()).exists():
        return 400, ErrorResponse(
            detail=f"设备 {payload.mac_address} 已存在",
            code="DEVICE_EXISTS",
        )

    # 创建设备
    user = request.user
    assert isinstance(user, User), "User must be authenticated"
    detector = Detector.objects.create(
        mac_address=payload.mac_address.upper(),
        name=payload.name,
        description=payload.description or "",
        owner=user,
    )

    logger.info("User %s created device %s", request.user.username, detector.mac_address)
    return 201, DetectorOut.from_orm(detector)


@router.get("/devices/{device_id}/", response=DetectorOut, tags=["Devices"])
def get_device(request: HttpRequest, device_id: int) -> DetectorOut:
    """获取设备详情"""
    user = request.user
    assert isinstance(user, User), "User must be authenticated"
    detector = get_object_or_404(
        Detector.objects.select_related("owner"),
        id=device_id,
        owner=user,
    )
    return DetectorOut.from_orm(detector)


@router.patch(
    "/devices/{device_id}/",
    response={200: DetectorOut, 404: ErrorResponse},
    tags=["Devices"],
)
def update_device(request: HttpRequest, device_id: int, payload: DetectorUpdate) -> DetectorOut:
    """更新设备信息"""
    user = request.user
    assert isinstance(user, User), "User must be authenticated"
    detector = get_object_or_404(Detector, id=device_id, owner=user)

    # 只更新非 None 的字段
    if payload.name is not None:
        detector.name = payload.name
    if payload.description is not None:
        detector.description = payload.description
    if payload.is_active is not None:
        detector.is_active = payload.is_active

    detector.save()
    logger.info("User %s updated device %s", request.user.username, detector.mac_address)

    return DetectorOut.from_orm(detector)


@router.delete(
    "/devices/{device_id}/",
    response={204: None, 404: ErrorResponse},
    tags=["Devices"],
)
def delete_device(request: HttpRequest, device_id: int) -> tuple[int, None]:
    """删除设备"""
    user = request.user
    assert isinstance(user, User), "User must be authenticated"
    detector = get_object_or_404(Detector, id=device_id, owner=user)
    mac_address = detector.mac_address

    detector.delete()
    logger.info("User %s deleted device %s", request.user.username, mac_address)

    return 204, None


# ============================================================================
# 数据包上传 API
# ============================================================================


@router.post(
    "/mu-packets/",
    response={200: PacketUploadResponse, 400: ErrorResponse, 404: ErrorResponse},
    tags=["Data Packets"],
)
def upload_packet(request: HttpRequest, payload: PacketUpload) -> PacketUploadResponse | tuple[int, ErrorResponse]:
    """
    上传数据包(Muon 或 Timeline)

    - 验证设备归属
    - 写入 IoTDB
    - 更新设备最后上报时间
    """
    # 验证设备存在且属于当前用户
    user = request.user
    assert isinstance(user, User), "User must be authenticated"
    try:
        detector = Detector.objects.get(
            mac_address=payload.device.upper(),
            owner=user,
        )
    except Detector.DoesNotExist:
        return 404, ErrorResponse(
            detail=f"设备 {payload.device} 不存在或不属于当前用户",
            code="DEVICE_NOT_FOUND",
        )

    # 验证数据包内容
    if payload.packet_type == "muon" and not payload.muon_packet:
        return 400, ErrorResponse(
            detail="packet_type 为 muon 时必须提供 muon_packet",
            code="INVALID_PACKET",
        )

    if payload.packet_type == "timeline" and not payload.timeline_packet:
        return 400, ErrorResponse(
            detail="packet_type 为 timeline 时必须提供 timeline_packet",
            code="INVALID_PACKET",
        )

    # 写入 IoTDB
    try:
        if payload.packet_type == "muon":
            assert payload.muon_packet is not None, "muon_packet is required"
            records_written = ingest_muon_packet(detector.mac_address, payload.muon_packet)
        else:  # timeline
            assert payload.timeline_packet is not None, "timeline_packet is required"
            records_written = ingest_timeline_packet(detector.mac_address, payload.timeline_packet)

        # 更新设备最后上报时间
        detector.last_seen_at = datetime.now(UTC)
        detector.save(update_fields=["last_seen_at"])

        logger.info(
            "Device %s uploaded %s packet: %d records",
            detector.mac_address,
            payload.packet_type,
            records_written,
        )

        return PacketUploadResponse(
            device=detector.mac_address,
            packet_type=payload.packet_type,
            records_written=records_written,
            message=f"成功写入 {records_written} 条记录",
        )

    except Exception:
        logger.exception(
            "Failed to process %s packet from %s",
            payload.packet_type,
            detector.mac_address,
        )
        return 400, ErrorResponse(
            detail="数据写入失败",
            code="IOTDB_WRITE_ERROR",
        )
