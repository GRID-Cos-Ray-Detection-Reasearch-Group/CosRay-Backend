"""
IoTDB 服务层: 负责时序数据写入和连接池管理
"""

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from django.conf import settings
from iotdb.SessionPool import SessionPool
from iotdb.utils.IoTDBConstants import TSDataType

if TYPE_CHECKING:
    from iotdb.Session import Session

from .schemas import MuonPacket
from .schemas import TimelinePacket

logger = logging.getLogger(__name__)


# ============================================================================
# 连接池管理
# ============================================================================


@lru_cache(maxsize=1)
def get_iotdb_pool() -> SessionPool:
    """
    获取 IoTDB SessionPool 单例
    使用 lru_cache 确保全局只创建一次连接池
    """
    pool = SessionPool(
        host=settings.IOTDB_HOST,
        port=settings.IOTDB_PORT,
        user=settings.IOTDB_USER,
        password=settings.IOTDB_PASSWORD,
        fetch_size=1024,
        max_size=5,  # 根据并发量调整
        timeout_ms=30000,
    )
    logger.info("IoTDB SessionPool 已创建: %s:%s", settings.IOTDB_HOST, settings.IOTDB_PORT)
    return pool


# ============================================================================
# 路径规范化
# ============================================================================


def normalize_device_path(mac_address: str) -> str:
    """
    将 MAC 地址转换为 IoTDB 路径格式

    例如: AA:BB:CC:DD:EE:FF -> root.cosray.AA_BB_CC_DD_EE_FF
    """
    sanitized = mac_address.strip().upper().replace(":", "_")
    return f"root.cosray.{sanitized}"


# ============================================================================
# Muon 数据写入
# ============================================================================


def ingest_muon_packet(device_mac: str, packet: MuonPacket) -> int:
    """
    将 Muon 数据包写入 IoTDB

    返回写入的记录数
    """
    if not packet.events:
        logger.warning("Muon packet from %s has no events", device_mac)
        return 0

    pool = get_iotdb_pool()
    session: Session = pool.get_session()

    try:
        device_path = normalize_device_path(device_mac)
        measurements = ["cpu_time", "energy", "pps"]
        data_types = [TSDataType.INT64, TSDataType.INT32, TSDataType.INT64]

        # 准备批量写入数据
        timestamps: list[int] = []
        values_list: list[list[int]] = [[], [], []]  # cpu_time, energy, pps

        for event in packet.events:
            # 计算时间戳: 使用包头 UTC + 事件的相对时间
            # 如果事件有 timestamp 字段, 使用它; 否则使用包头 UTC * 1000
            ts = event.timestamp if event.timestamp else packet.utc * 1000
            timestamps.append(ts)

            values_list[0].append(event.cpu_time)
            values_list[1].append(event.energy)
            values_list[2].append(event.pps)

        # 批量写入
        session.insert_records(
            device_ids=[device_path] * len(timestamps),
            timestamps_list=timestamps,
            measurements_list=[measurements] * len(timestamps),
            types_list=[data_types] * len(timestamps),
            values_list=[[values_list[i][j] for i in range(3)] for j in range(len(timestamps))],
        )

        logger.info("Muon packet from %s written: %d records", device_mac, len(timestamps))
        return len(timestamps)

    except Exception:
        logger.exception("Failed to write Muon packet from %s", device_mac)
        raise

    finally:
        pool.put_back(session)


# ============================================================================
# Timeline 数据写入
# ============================================================================


def ingest_timeline_packet(device_mac: str, packet: TimelinePacket) -> int:
    """
    将 Timeline 数据包写入 IoTDB

    返回写入的记录数
    """
    if not packet.events:
        logger.warning("Timeline packet from %s has no events", device_mac)
        return 0

    pool = get_iotdb_pool()
    session: Session = pool.get_session()

    try:
        device_path = normalize_device_path(device_mac)

        # Timeline 指标更多
        measurements = [
            "cpu_time",
            "pps",
            "utc",
            "pps_utc",
            "cputime_pps",
            "gps_long",
            "gps_lat",
            "gps_alt",
            "acc_x",
            "acc_y",
            "acc_z",
            "sipm_tmp",
            "mcu_tmp",
            "sipm_imon",
            "sipm_vmon",
        ]

        data_types = [
            TSDataType.INT64,  # cpu_time
            TSDataType.INT64,  # pps
            TSDataType.INT64,  # utc
            TSDataType.INT64,  # pps_utc
            TSDataType.INT64,  # cputime_pps
            TSDataType.INT32,  # gps_long
            TSDataType.INT32,  # gps_lat
            TSDataType.INT32,  # gps_alt
            TSDataType.INT32,  # acc_x
            TSDataType.INT32,  # acc_y
            TSDataType.INT32,  # acc_z
            TSDataType.INT32,  # sipm_tmp
            TSDataType.INT32,  # mcu_tmp
            TSDataType.INT32,  # sipm_imon
            TSDataType.INT32,  # sipm_vmon
        ]

        # 准备批量写入数据
        timestamps: list[int] = []
        values_list: list[list[int]] = [[] for _ in range(len(measurements))]

        for event in packet.events:
            # 使用事件的 UTC 时间戳(转毫秒)
            ts = event.timestamp if event.timestamp else event.utc * 1000
            timestamps.append(ts)

            values_list[0].append(event.cpu_time)
            values_list[1].append(event.pps)
            values_list[2].append(event.utc)
            values_list[3].append(event.pps_utc)
            values_list[4].append(event.cputime_pps)
            values_list[5].append(event.gps_long)
            values_list[6].append(event.gps_lat)
            values_list[7].append(event.gps_alt)
            values_list[8].append(event.acc_x)
            values_list[9].append(event.acc_y)
            values_list[10].append(event.acc_z)
            values_list[11].append(event.sipm_tmp)
            values_list[12].append(event.mcu_tmp)
            values_list[13].append(event.sipm_imon)
            values_list[14].append(event.sipm_vmon)

        # 批量写入
        session.insert_records(
            device_ids=[device_path] * len(timestamps),
            timestamps_list=timestamps,
            measurements_list=[measurements] * len(timestamps),
            types_list=[data_types] * len(timestamps),
            values_list=[[values_list[i][j] for i in range(len(measurements))] for j in range(len(timestamps))],
        )

        logger.info(
            "Timeline packet from %s written: %d records",
            device_mac,
            len(timestamps),
        )
        return len(timestamps)

    except Exception:
        logger.exception("Failed to write Timeline packet from %s", device_mac)
        raise

    finally:
        pool.put_back(session)
