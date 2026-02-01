from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Detector


@admin.register(Detector)
class DetectorAdmin(ModelAdmin):  # type: ignore[misc]
    """探测器管理后台"""

    list_display = [
        "mac_address",
        "name",
        "owner",
        "is_active",
        "last_seen_at",
        "created_at",
    ]

    list_filter = [
        "is_active",
        "created_at",
        "last_seen_at",
    ]

    search_fields = [
        "mac_address",
        "name",
        "owner__username",
        "owner__email",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "基本信息",
            {
                "fields": ("mac_address", "name", "owner", "description"),
            },
        ),
        (
            "状态",
            {
                "fields": ("is_active", "last_seen_at"),
            },
        ),
        (
            "时间信息",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):  # type: ignore[no-untyped-def]
        qs = super().get_queryset(request)
        return qs.select_related("owner")
