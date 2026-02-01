"""
Pydantic schemas for API request/response validation
"""

from datetime import datetime
from typing import Any
from typing import Literal

from ninja import Schema

# ============================================================================
# 设备相关 Schemas
# ============================================================================


class DetectorOut(Schema):
    """设备输出模型"""

    id: int
    mac_address: str
    name: str
    description: str | None
    is_active: bool
    owner_id: int
    owner_username: str
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None

    @classmethod
    def from_orm(cls, detector: Any) -> "DetectorOut":  # type: ignore[override]
        """从 ORM 对象转换"""
        return DetectorOut(
            id=detector.id,
            mac_address=detector.mac_address,
            name=detector.name,
            description=detector.description or None,
            is_active=detector.is_active,
            owner_id=detector.owner_id,
            owner_username=detector.owner.username,
            created_at=detector.created_at,
            updated_at=detector.updated_at,
            last_seen_at=detector.last_seen_at,
        )


class DetectorCreate(Schema):
    """设备创建请求"""

    mac_address: str
    name: str
    description: str | None = None


class DetectorUpdate(Schema):
    """设备更新请求"""

    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


# ============================================================================
# 数据包相关 Schemas - Muon Packet
# ============================================================================


class MuonEvent(Schema):
    """单个 Muon 事件"""

    cpu_time: int  # uint64
    energy: int  # uint16 ADC 值
    pps: int  # uint32 PPS 脉冲计数
    timestamp: int | None = None  # 可选的毫秒级时间戳


class MuonPacket(Schema):
    """Muon 数据包 (35 个事件)"""

    package_counter: int  # uint32 全局包计数
    utc: int  # uint32 首事件 UTC 时间戳 (秒)
    events: list[MuonEvent]  # 最多 35 个事件
    head: list[int] | None = None  # [0xAA, 0xBB, 0xCC]
    tail: list[int] | None = None  # [0xDD, 0xEE, 0xFF]
    crc: int | None = None  # uint16 校验


# ============================================================================
# 数据包相关 Schemas - Timeline Packet
# ============================================================================


class TimelineEvent(Schema):
    """单个 Timeline 事件"""

    cpu_time: int  # uint64
    pps: int  # uint32
    utc: int  # uint32 UTC 时间戳 (秒)
    pps_utc: int  # uint32 上次 UTC 的 PPS
    cputime_pps: int  # uint64 上次 PPS 的 CPU 时钟
    gps_long: int  # int32 GPS 经度
    gps_lat: int  # int32 GPS 纬度
    gps_alt: int  # int16 GPS 海拔
    acc_x: int  # int8 X 轴加速度
    acc_y: int  # int8 Y 轴加速度
    acc_z: int  # int8 Z 轴加速度
    sipm_tmp: int  # uint16 SiPM 温度
    mcu_tmp: int  # uint8 MCU 温度
    sipm_imon: int  # uint16 SiPM 漏电流
    sipm_vmon: int  # uint16 SiPM 偏压
    timestamp: int | None = None  # 可选的毫秒级时间戳


class TimelinePacket(Schema):
    """Timeline 数据包 (10 个事件)"""

    package_counter: int  # uint32 全局包计数
    events: list[TimelineEvent]  # 最多 10 个事件
    head: list[int] | None = None  # [0x12, 0x34, 0x56]
    tail: list[int] | None = None  # [0x78, 0x9A, 0xBC]
    crc: int | None = None  # uint16 校验


# ============================================================================
# 数据包上传 Schemas
# ============================================================================


class PacketUpload(Schema):
    """数据包上传请求"""

    device: str  # MAC 地址
    packet_type: Literal["muon", "timeline"]
    muon_packet: MuonPacket | None = None
    timeline_packet: TimelinePacket | None = None


class PacketUploadResponse(Schema):
    """数据包上传响应"""

    device: str
    packet_type: str
    records_written: int  # 写入 IoTDB 的记录数
    message: str


# ============================================================================
# 错误响应 Schemas
# ============================================================================


class ErrorResponse(Schema):
    """统一错误响应"""

    detail: str
    code: str | None = None
