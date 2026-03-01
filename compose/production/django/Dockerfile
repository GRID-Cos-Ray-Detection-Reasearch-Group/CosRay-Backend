# CosRay-Backend Production Dockerfile
# 多阶段构建：优化镜像大小和安全性

# ============ 阶段 1: Python Build Stage ============
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS python-build-stage

# Metadata
LABEL maintainer="GRID Group <grid@example.com>"
LABEL org.opencontainers.image.source="https://github.com/GRID-Cos-Ray-Detection-Reasearch-Group/CosRay-Backend"
LABEL org.opencontainers.image.description="CosRay Backend - Production Build Stage"
LABEL org.opencontainers.image.version="1.0.0"

ARG APP_HOME=/app

WORKDIR ${APP_HOME}

# UV 环境变量
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_INDEX_URL=https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple

# 配置 Debian TUNA 源（加速 apt）
RUN sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources

# 一并执行安装依赖(由于使用了 build-essential 等，编译 C 依赖要在同一层完成再 purge)
# 使用 uv sync 安装依赖（利用 cache mount 加速）
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    libpq-dev \
    && uv sync --frozen --no-install-project --no-dev \
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*



# ============ 阶段 2: Python Runtime Stage ============
FROM python:3.13-slim-bookworm AS python-run-stage

# Metadata
LABEL maintainer="GRID Group <grid@example.com>"
LABEL org.opencontainers.image.source="https://github.com/GRID-Cos-Ray-Detection-Reasearch-Group/CosRay-Backend"
LABEL org.opencontainers.image.description="CosRay Backend - Production Runtime"
LABEL org.opencontainers.image.version="1.0.0"

ARG APP_HOME=/app

WORKDIR ${APP_HOME}

# Python 优化环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PATH="${APP_HOME}/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings

# 配置 Debian TUNA 源（加速 apt）
RUN sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources

# 创建 Django 用户
RUN addgroup --system django && \
    adduser --system --ingroup django django

# 安装运行时依赖
RUN apt-get update && apt-get install --no-install-recommends -y \
    curl \
    gettext \
    libpq-dev \
    wait-for-it \
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制应用代码和虚拟环境
COPY --from=python-build-stage --chown=django:django ${APP_HOME} ${APP_HOME}

# 复制并设置 entrypoint 脚本
COPY --chown=django:django ./compose/production/django/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint && chmod +x /entrypoint

# 复制并设置 start 脚本
COPY --chown=django:django ./compose/production/django/start /start
RUN sed -i 's/\r$//g' /start && chmod +x /start

# 创建静态文件和媒体目录
RUN mkdir -p ${APP_HOME}/staticfiles ${APP_HOME}/media && \
    chown -R django:django ${APP_HOME}

# 切换到非 root 用户
USER django

# 编译国际化消息（构建时执行）
RUN DATABASE_URL="" \
    DJANGO_SETTINGS_MODULE="config.settings" \
    SECRET_KEY="dummy" \
    ALLOWED_HOSTS="localhost" \
    python manage.py compilemessages || true

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# 暴露端口
EXPOSE 5000

ENTRYPOINT ["/entrypoint"]
