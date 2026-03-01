# CosRay-Backend Local Development Dockerfile
# 包含开发工具和热重载支持

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS python

# Metadata
LABEL maintainer="GRID Group <grid@example.com>"
LABEL org.opencontainers.image.source="https://github.com/GRID-Cos-Ray-Detection-Reasearch-Group/CosRay-Backend"
LABEL org.opencontainers.image.description="CosRay Backend - Local Development"
LABEL org.opencontainers.image.version="1.0.0"

ARG APP_HOME=/workspace

WORKDIR ${APP_HOME}

# 环境变量 - Python 优化
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_INDEX_URL=https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings

# 配置 Debian TUNA 源（加速 apt）
RUN sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources

# 安装构建与运行依赖，并在同一层运行 uv sync 再 purge C 头文件等不需要的缓存
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock,readonly \
    apt-get update && \
    apt-get install --no-install-recommends -y \
    bash-completion \
    build-essential \
    curl \
    gettext \
    git \
    libpq-dev \
    nano \
    ssh \
    sudo \
    vim \
    wait-for-it && \
    uv sync --no-install-project --frozen && \
    apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false && \
    rm -rf /var/lib/apt/lists/*

# 创建开发用户并设置权限
RUN groupadd --gid 1000 dev-user && \
    useradd --uid 1000 --gid dev-user --shell /bin/bash --create-home dev-user && \
    echo "dev-user ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/dev-user && \
    chmod 0440 /etc/sudoers.d/dev-user && \
    chown -R dev-user:dev-user ${APP_HOME}

# 复制并设置 entrypoint 脚本
COPY ./compose/production/django/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint && chmod +x /entrypoint

# 复制并设置 start 脚本
COPY ./compose/local/django/start /start
RUN sed -i 's/\r$//g' /start && chmod +x /start

# 暴露开发服务器端口
EXPOSE 8000

ENTRYPOINT ["/entrypoint"]
