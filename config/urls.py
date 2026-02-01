"""
URL configuration for CosRay-Backend
"""

from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI
from ninja_jwt.routers.obtain import obtain_pair_router
from ninja_jwt.routers.verify import verify_router

from core.api import router as core_router

# 创建 NinjaAPI 实例
api = NinjaAPI(
    title="CosRay Backend API",
    version="1.0.0",
    description="宇宙射线探测系统后端 API",
)

# 注册 JWT 路由
api.add_router("/token/", tags=["Authentication"], router=obtain_pair_router)
api.add_router("/token/", tags=["Authentication"], router=verify_router)

# 注册核心业务路由
api.add_router("", core_router)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
