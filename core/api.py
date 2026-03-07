"""
Django Ninja API 路由
"""

import logging
from datetime import UTC
from datetime import datetime
from typing import cast
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.exceptions import TokenError
from ninja_jwt.tokens import RefreshToken

from .models import Detector
from .schemas import CurrentUserOut
from .schemas import DetectorCreate
from .schemas import DetectorOut
from .schemas import DetectorUpdate
from .schemas import ErrorResponse
from .schemas import PacketUpload
from .schemas import PacketUploadResponse
from .schemas import RegisterResponse
from .schemas import TokenPairIn
from .schemas import TokenPairOut
from .schemas import TokenRefreshIn
from .schemas import TokenRefreshOut
from .schemas import UserRegisterSchema
from .security import check_rate_limit
from .security import get_client_ip
from .security import refresh_token_is_revoked
from .security import revoke_refresh_token
from .services import IoTDBWriteError
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


@router.post("/auth/register", response=RegisterResponse, auth=None, tags=["Auth"])
def register_user(request: HttpRequest, payload: UserRegisterSchema) -> RegisterResponse:
    """用户注册并返回 JWT"""
    rate_limit_error = check_rate_limit(
        scope="register",
        identifier=get_client_ip(request),
        limit=settings.REGISTER_RATE_LIMIT_COUNT,
        window_seconds=settings.REGISTER_RATE_LIMIT_WINDOW_SECONDS,
    )
    if rate_limit_error is not None:
        raise HttpError(429, rate_limit_error.detail)

    username = payload.username.strip()
    email = payload.email.strip().lower()
    password = payload.password

    if not username or not email or not password:
        raise HttpError(400, "用户名、邮箱和密码不能为空")

    if User.objects.filter(username=username).exists() or User.objects.filter(email=email).exists():
        raise HttpError(409, "注册信息不可用")

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
    )
    access_token, refresh_token = build_token_pair(user)

    return RegisterResponse(
        access=access_token,
        refresh=refresh_token,
        user=CurrentUserOut(id=user.id, username=user.username, email=user.email),
    )


@router.post(
    "/token/pair",
    response={200: TokenPairOut, 401: ErrorResponse, 429: ErrorResponse},
    auth=None,
    tags=["Auth"],
)
def obtain_token_pair(request: HttpRequest, payload: TokenPairIn) -> TokenPairOut | tuple[int, ErrorResponse]:
    """登录并签发 access/refresh token。"""
    username = payload.username.strip()
    rate_limit_error = check_rate_limit(
        scope="login",
        identifier=f"{get_client_ip(request)}:{username.lower()}",
        limit=settings.LOGIN_RATE_LIMIT_COUNT,
        window_seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )
    if rate_limit_error is not None:
        return 429, rate_limit_error

    user = authenticate(request, username=username, password=payload.password)
    if not isinstance(user, User) or not user.is_active:
        return 401, ErrorResponse(detail="用户名或密码错误", code="INVALID_CREDENTIALS")

    access_token, refresh_token = build_token_pair(user)
    return TokenPairOut(access=access_token, refresh=refresh_token)


@router.post(
    "/token/refresh",
    response={200: TokenRefreshOut, 401: ErrorResponse},
    auth=None,
    tags=["Auth"],
)
def refresh_token(request: HttpRequest, payload: TokenRefreshIn) -> TokenRefreshOut | tuple[int, ErrorResponse]:
    """刷新 access token，并使旧 refresh token 失效。"""
    del request
    try:
        refresh = RefreshToken(payload.refresh)
        refresh.verify()  # type: ignore[no-untyped-call]
    except TokenError:
        return 401, ErrorResponse(detail="Refresh Token 无效", code="INVALID_TOKEN")

    if refresh_token_is_revoked(refresh):
        return 401, ErrorResponse(detail="Refresh Token 无效", code="INVALID_TOKEN")

    user_id = refresh.get(settings.NINJA_JWT["USER_ID_CLAIM"])
    if not isinstance(user_id, int):
        return 401, ErrorResponse(detail="Refresh Token 无效", code="INVALID_TOKEN")

    try:
        user = User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        return 401, ErrorResponse(detail="Refresh Token 无效", code="INVALID_TOKEN")

    if settings.NINJA_JWT.get("BLACKLIST_AFTER_ROTATION", False):
        revoke_refresh_token(refresh)

    access_token, refresh_token_value = build_token_pair(user)
    return TokenRefreshOut(access=access_token, refresh=refresh_token_value)


def resolve_request_id(request: HttpRequest) -> str:
    """提取请求 ID，若缺失则生成"""
    request_id = request.headers.get("X-Request-ID", "").strip()
    if request_id:
        return request_id
    return uuid4().hex


def format_log_context(**kwargs: str | int) -> str:
    """格式化结构化日志上下文"""
    return " ".join(f"{key}={value}" for key, value in kwargs.items())


def build_token_pair(user: User) -> tuple[str, str]:
    """为用户签发新的 access/refresh token。"""
    refresh = cast("RefreshToken", RefreshToken.for_user(user))
    return str(refresh.access_token), str(refresh)


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


def ingest_packet_for_detector(
    payload: PacketUpload,
    detector_mac_address: str,
) -> tuple[int | None, ErrorResponse | None]:
    """根据 packet_type 写入对应数据包。"""
    if payload.packet_type == "muon":
        if payload.muon_packet is None:
            return None, ErrorResponse(detail="packet_type 为 muon 时必须提供 muon_packet", code="INVALID_PACKET")
        return ingest_muon_packet(detector_mac_address, payload.muon_packet), None

    if payload.timeline_packet is None:
        return None, ErrorResponse(
            detail="packet_type 为 timeline 时必须提供 timeline_packet",
            code="INVALID_PACKET",
        )
    return ingest_timeline_packet(detector_mac_address, payload.timeline_packet), None


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
    if normalized_mac is None:
        logger.error("create_device_missing_normalized_mac request_id=%s", request_id)
        return 400, ErrorResponse(detail="MAC 地址格式必须为 AA:BB:CC:DD:EE:FF", code="INVALID_MAC_ADDRESS")

    # 检查 MAC 地址是否已存在
    if Detector.objects.filter(mac_address=normalized_mac).exists():
        user = resolve_authenticated_user(request)
        logger.warning(
            "create_device_duplicate %s",
            format_log_context(
                request_id=request_id,
                user_id=user.id,
                mac_address=normalized_mac,
                error_code="DEVICE_REGISTRATION_UNAVAILABLE",
            ),
        )
        return 400, ErrorResponse(
            detail="设备无法注册",
            code="DEVICE_REGISTRATION_UNAVAILABLE",
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
    response={200: PacketUploadResponse, 400: ErrorResponse, 404: ErrorResponse, 429: ErrorResponse},
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
    if normalized_mac is None:
        logger.error("upload_packet_missing_normalized_mac request_id=%s", request_id)
        return 400, ErrorResponse(detail="MAC 地址格式必须为 AA:BB:CC:DD:EE:FF", code="INVALID_MAC_ADDRESS")

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
    if detector is None:
        logger.error(
            "upload_packet_missing_detector %s",
            format_log_context(
                request_id=request_id,
                user_id=user.id,
                mac_address=normalized_mac,
                error_code="DEVICE_NOT_FOUND",
            ),
        )
        return 404, ErrorResponse(
            detail=f"设备 {normalized_mac} 不存在或不属于当前用户",
            code="DEVICE_NOT_FOUND",
        )

    rate_limit_error = check_rate_limit(
        scope="upload",
        identifier=f"{user.id}:{detector.mac_address}",
        limit=settings.UPLOAD_RATE_LIMIT_COUNT,
        window_seconds=settings.UPLOAD_RATE_LIMIT_WINDOW_SECONDS,
    )
    if rate_limit_error is not None:
        return 429, rate_limit_error

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
        records_written, packet_error = ingest_packet_for_detector(payload, detector.mac_address)
        if packet_error is not None:
            return 400, packet_error
        if records_written is None:
            return 400, ErrorResponse(detail="数据包内容无效", code="INVALID_PACKET")

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

    except IoTDBWriteError:
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
