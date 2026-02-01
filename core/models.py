from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


class Detector(models.Model):
    """探测器设备模型"""

    mac_address = models.CharField(
        max_length=17,
        unique=True,
        validators=[
            RegexValidator(
                regex=r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$",
                message="MAC 地址格式必须为 AA:BB:CC:DD:EE:FF",
            )
        ],
        verbose_name="MAC 地址",
        help_text="设备唯一标识, 格式: AA:BB:CC:DD:EE:FF",
    )

    name = models.CharField(
        max_length=100,
        verbose_name="设备名称",
        help_text="用户自定义的设备名称",
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="detectors",
        verbose_name="所有者",
    )

    description = models.TextField(
        blank=True,
        verbose_name="描述",
        help_text="设备描述信息",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="激活状态",
        help_text="设备是否处于激活状态",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新时间",
    )

    last_seen_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="最后上报时间",
        help_text="最后一次接收到数据的时间",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "探测器"
        verbose_name_plural = "探测器"
        indexes = [
            models.Index(fields=["owner", "-created_at"]),
            models.Index(fields=["is_active", "-last_seen_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.mac_address})"
