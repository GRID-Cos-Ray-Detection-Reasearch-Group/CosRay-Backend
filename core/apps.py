from typing import Any

from django.apps import AppConfig
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_migrate


def auto_create_test_user(sender: Any, **kwargs: Any) -> None:
    """
    开发环境下，在执行完 migrate 之后，自动创建与 App 测试页面配套的账号。
    仅当 settings.DEBUG=True 时会生效。
    """
    if not settings.DEBUG:
        return

    user_model = get_user_model()

    test_username = "test"
    test_password = "LocalPass123!"
    test_email = "test@example.com"

    user, created = user_model.objects.get_or_create(
        username=test_username,
        defaults={
            "email": test_email,
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )

    # 始终重置密码，防止密码哈希改变或被手动修改后导致 App 端用预设密码登录失败
    user.set_password(test_password)
    user.save(update_fields=["password"])

    action = "Created" if created else "Updated password for"
    print(f"[{sender.name}] {action} local dev test user: {test_username}")


class CoreConfig(AppConfig):
    name = "core"

    def ready(self) -> None:
        # 绑定迁移后信号，无 sender，并通过 dispatch_uid 保证全项目仅注册一次该回调
        post_migrate.connect(auto_create_test_user, dispatch_uid="core_auto_create_test_user")
