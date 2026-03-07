from django.contrib import admin
from django.contrib.auth.models import User
from django.db.models import QuerySet
from django.http import HttpRequest
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

    def get_queryset(self, request: HttpRequest) -> QuerySet[Detector]:
        base_queryset = super().get_queryset(request)
        qs = Detector.objects.filter(pk__in=base_queryset.values("pk")).select_related("owner")
        user = request.user
        if bool(getattr(user, "is_superuser", False)):
            return qs
        if not isinstance(user, User):
            return qs.none()
        return qs.filter(owner=user)

    def get_exclude(self, request: HttpRequest, obj: Detector | None = None) -> tuple[str, ...] | None:
        user = request.user
        if bool(getattr(user, "is_superuser", False)):
            return None
        return ("owner",)

    def save_model(self, request: HttpRequest, obj: Detector, form, change: bool) -> None:  # type: ignore[no-untyped-def]  # noqa: FBT001
        user = request.user
        if isinstance(user, User) and not user.is_superuser:
            obj.owner = user
        super().save_model(request, obj, form, change)

    def has_view_permission(self, request: HttpRequest, obj: Detector | None = None) -> bool:
        has_permission = bool(super().has_view_permission(request, obj))
        user = request.user
        if not has_permission or obj is None or bool(getattr(user, "is_superuser", False)):
            return has_permission
        return bool(obj.owner == user)

    def has_change_permission(self, request: HttpRequest, obj: Detector | None = None) -> bool:
        has_permission = bool(super().has_change_permission(request, obj))
        user = request.user
        if not has_permission or obj is None or bool(getattr(user, "is_superuser", False)):
            return has_permission
        return bool(obj.owner == user)

    def has_delete_permission(self, request: HttpRequest, obj: Detector | None = None) -> bool:
        has_permission = bool(super().has_delete_permission(request, obj))
        user = request.user
        if not has_permission or obj is None or bool(getattr(user, "is_superuser", False)):
            return has_permission
        return bool(obj.owner == user)
