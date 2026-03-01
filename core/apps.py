from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_migrate


def auto_create_test_user(sender, **kwargs):
    """
    开发环境下，在执行完 migrate 之后，自动创建与 App 测试页面配套的账号。
    仅当 settings.DEBUG=True 时会生效。
    """
    if not settings.DEBUG:
        return

    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    test_username = "test"
    test_password = "LocalPass123!"
    test_email = "test@example.com"
    
    if not User.objects.filter(username=test_username).exists():
        User.objects.create_superuser(
            username=test_username,
            email=test_email,
            password=test_password,
        )


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        # 绑定迁移后信号
        post_migrate.connect(auto_create_test_user, sender=self)

