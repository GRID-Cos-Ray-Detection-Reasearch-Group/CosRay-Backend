"""
URL configuration for CosRay-Backend
"""

from django.contrib import admin
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import JsonResponse
from django.urls import path
from ninja import NinjaAPI
from ninja.errors import HttpError
from ninja.errors import ValidationError
from ninja_jwt.routers.verify import verify_router

from core.api import router as core_router
from core.errors import build_error

# 创建 NinjaAPI 实例
api = NinjaAPI(
    title="CosRay Backend API",
    version="1.0.0",
    description="宇宙射线探测系统后端 API",
)


@api.exception_handler(ValidationError)
def on_validation_error(request: HttpRequest, exc: ValidationError) -> HttpResponse:
    request_id = getattr(request, "request_id", "")
    if not isinstance(request_id, str) or not request_id.strip():
        request_id = "unknown"
    error = build_error(detail="请求参数校验失败", code="INVALID_PAYLOAD", request_id=request_id)
    return JsonResponse(error.model_dump(), status=400)


@api.exception_handler(HttpError)
def on_http_error(request: HttpRequest, exc: HttpError) -> HttpResponse:
    request_id = getattr(request, "request_id", "")
    if not isinstance(request_id, str) or not request_id.strip():
        request_id = "unknown"

    if exc.status_code == 401:
        error = build_error(detail="需要认证", code="UNAUTHORIZED", request_id=request_id)
    else:
        error = build_error(detail=str(exc), code=None, request_id=request_id)
    return JsonResponse(error.model_dump(), status=exc.status_code)


# 注册 JWT 路由
api.add_router("/token/", tags=["Authentication"], router=verify_router)

# 注册核心业务路由
api.add_router("", core_router)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
