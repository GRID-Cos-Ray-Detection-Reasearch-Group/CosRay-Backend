"""
Django Ninja API 路由
"""

import logging
from datetime import UTC
from datetime import datetime
from uuid import uuid4

from django.contrib.auth.models import User
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth

from .models import Detector
from .schemas import CurrentUserOut
from .schemas import DetectorCreate
from .schemas import DetectorOut
from .schemas import DetectorUpdate
from .schemas import ErrorResponse
from .schemas import PacketUpload
from .schemas import PacketUploadResponse
from .services import ingest_muon_packet
from .services import ingest_timeline_packet
from .validators import normalize_mac_or_error
from .validators import validate_packet_payload

logger = logging.getLogger(__name__)

# 创建路由器, 默认使用 JWT 认证
router = Router(auth=JWTAuth())


@router.get("/health", auth=None, tags=["System"])
def health_check(request: HttpRequest) -> dict[str, str]:
    """容器与负载均衡健康检查端点"""
    return {"status": "ok"}


def resolve_request_id(request: HttpRequest) -> str:
    """提取请求 ID，若缺失则生成"""
    request_id = request.headers.get("X-Request-ID", "").strip()
    if request_id:
        return request_id
    return uuid4().hex


def format_log_context(**kwargs: str | int) -> str:
    """格式化结构化日志上下文"""
    return " ".join(f"{key}={value}" for key, value in kwargs.items())


def resolve_authenticated_user(request: HttpRequest) -> User:
    """统一提取已认证用户，未认证则抛出 401"""
    user = request.user
    if not isinstance(user, User):
        raise HttpError(401, "User must be authenticated")
    return user


def get_owned_detector_or_error(user: User, mac_address: str) -> tuple[Detector | None, ErrorResponse | None]:
    """按 owner + MAC 获取设备"""
    try:
        detector = Detector.objects.get(mac_address=mac_address, owner=user)
    except Detector.DoesNotExist:
        return None, ErrorResponse(
            detail=f"设备 {mac_address} 不存在或不属于当前用户",
            code="DEVICE_NOT_FOUND",
        )
    return detector, None


@router.get("/users/me", response=CurrentUserOut, tags=["Users"])
def get_current_user(request: HttpRequest) -> CurrentUserOut:
    """获取当前登录用户信息"""
    user = resolve_authenticated_user(request)
    return CurrentUserOut(
        id=user.id,
        username=user.username,
        email=user.email,
    )


# ============================================================================
# 设备管理 API
# ============================================================================


@router.get("/devices/", response=list[DetectorOut], tags=["Devices"])
def list_devices(request: HttpRequest) -> list[DetectorOut]:
    """获取当前用户的所有设备"""
    user = resolve_authenticated_user(request)
    detectors = Detector.objects.filter(owner=user).select_related("owner")
    return [DetectorOut.from_orm(d) for d in detectors]


@router.post(
    "/devices/",
    response={201: DetectorOut, 400: ErrorResponse},
    tags=["Devices"],
)
def create_device(request: HttpRequest, payload: DetectorCreate) -> tuple[int, DetectorOut | ErrorResponse]:
    """注册新设备"""
    request_id = resolve_request_id(request)
    normalized_mac, mac_error = normalize_mac_or_error(payload.mac_address)
    if mac_error is not None:
        logger.warning(
            "create_device_invalid_mac %s",
            format_log_context(
                request_id=request_id,
                user_id=resolve_authenticated_user(request).id,
                input_mac=payload.mac_address,
                error_code=mac_error.code or "UNKNOWN",
            ),
        )
        return 400, mac_error
    assert normalized_mac is not None, "normalized_mac should not be None"

    # 检查 MAC 地址是否已存在
    if Detector.objects.filter(mac_address=normalized_mac).exists():
        user = resolve_authenticated_user(request)
        logger.warning(
            "create_device_duplicate %s",
            format_log_context(
                request_id=request_id,
                user_id=user.id,
                mac_address=normalized_mac,
                error_code="DEVICE_EXISTS",
            ),
        )
        return 400, ErrorResponse(
            detail=f"设备 {normalized_mac} 已存在",
            code="DEVICE_EXISTS",
        )

    # 创建设备
    user = resolve_authenticated_user(request)
    detector = Detector.objects.create(
        mac_address=normalized_mac,
        name=payload.name,
        description=payload.description or "",
        owner=user,
    )

    logger.info(
        "create_device_success %s",
        format_log_context(
            request_id=request_id,
            user_id=user.id,
            mac_address=detector.mac_address,
            device_id=detector.id,
        ),
    )
    return 201, DetectorOut.from_orm(detector)


@router.get("/devices/{device_id}/", response=DetectorOut, tags=["Devices"])
def get_device(request: HttpRequest, device_id: int) -> DetectorOut:
    """获取设备详情"""
    user = resolve_authenticated_user(request)
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
    request_id = resolve_request_id(request)
    user = resolve_authenticated_user(request)
    detector = get_object_or_404(Detector, id=device_id, owner=user)

    # 只更新非 None 的字段
    if payload.name is not None:
        detector.name = payload.name
    if payload.description is not None:
        detector.description = payload.description
    if payload.is_active is not None:
        detector.is_active = payload.is_active

    detector.save()
    logger.info(
        "update_device_success %s",
        format_log_context(
            request_id=request_id,
            user_id=user.id,
            device_id=device_id,
            mac_address=detector.mac_address,
        ),
    )

    return DetectorOut.from_orm(detector)


@router.delete(
    "/devices/{device_id}/",
    response={204: None, 404: ErrorResponse},
    tags=["Devices"],
)
def delete_device(request: HttpRequest, device_id: int) -> tuple[int, None]:
    """删除设备"""
    request_id = resolve_request_id(request)
    user = resolve_authenticated_user(request)
    detector = get_object_or_404(Detector, id=device_id, owner=user)
    mac_address = detector.mac_address

    detector.delete()
    logger.info(
        "delete_device_success %s",
        format_log_context(
            request_id=request_id,
            user_id=user.id,
            device_id=device_id,
            mac_address=mac_address,
        ),
    )

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
    request_id = resolve_request_id(request)
    normalized_mac, mac_error = normalize_mac_or_error(payload.device)
    if mac_error is not None:
        logger.warning(
            "upload_packet_invalid_mac %s",
            format_log_context(
                request_id=request_id,
                input_mac=payload.device,
                error_code=mac_error.code or "UNKNOWN",
            ),
        )
        return 400, mac_error
    assert normalized_mac is not None, "normalized_mac should not be None"

    user = resolve_authenticated_user(request)
    detector, detector_error = get_owned_detector_or_error(user, normalized_mac)
    if detector_error is not None:
        logger.warning(
            "upload_packet_detector_not_found %s",
            format_log_context(
                request_id=request_id,
                user_id=user.id,
                mac_address=normalized_mac,
                error_code=detector_error.code or "UNKNOWN",
            ),
        )
        return 404, detector_error
    assert detector is not None, "detector should not be None"

    payload_error = validate_packet_payload(payload)
    if payload_error is not None:
        logger.warning(
            "upload_packet_invalid_payload %s",
            format_log_context(
                request_id=request_id,
                user_id=user.id,
                mac_address=detector.mac_address,
                packet_type=payload.packet_type,
                error_code=payload_error.code or "UNKNOWN",
            ),
        )
        return 400, payload_error

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
            "upload_packet_success %s",
            format_log_context(
                request_id=request_id,
                user_id=user.id,
                mac_address=detector.mac_address,
                packet_type=payload.packet_type,
                records_written=records_written,
            ),
        )

        return PacketUploadResponse(
            device=detector.mac_address,
            device_name=detector.name,
            packet_type=payload.packet_type,
            records_written=records_written,
            message=f"成功写入 {records_written} 条记录",
        )

    except Exception:
        logger.exception(
            "upload_packet_iotdb_error %s",
            format_log_context(
                request_id=request_id,
                user_id=user.id,
                mac_address=detector.mac_address,
                packet_type=payload.packet_type,
                error_code="IOTDB_WRITE_ERROR",
            ),
        )
        return 400, ErrorResponse(
            detail="数据写入失败",
            code="IOTDB_WRITE_ERROR",
        )
