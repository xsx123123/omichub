# syntax=docker/dockerfile:1.7
# OmicStudio 独立浏览器/文档能力镜像。
# 先构建 base，再执行：
ARG CYGNUSX_IMAGE_TAG=v0.0.2dev
# docker build --build-arg CYGNUSX_IMAGE_TAG=v0.0.2dev \
#   -t cygnusx-sandbox-browser-office:v0.0.2dev \
#   -f deploy/studio/browser-office.Dockerfile deploy/studio
FROM cygnusx-sandbox-bio:${CYGNUSX_IMAGE_TAG}

ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ARG PIP_TIMEOUT=60
ARG PIP_RETRIES=5

USER root
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers \
    CHROME_BIN=/usr/bin/chromium \
    PYTHONPATH=/opt/sandbox \
    TMPDIR=/tmp/chromium \
    ONLYOFFICE_DOCUMENT_SERVER_URL=http://onlyoffice-documentserver

# 构建期切换中科大 apt 源，加速 apt-get（兼容 debian.sources 与旧版 sources.list）
RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's@//deb.debian.org@//mirrors.ustc.edu.cn@g; s@//security.debian.org@//mirrors.ustc.edu.cn@g' /etc/apt/sources.list.d/debian.sources; \
    else \
        sed -i 's@//deb.debian.org@//mirrors.ustc.edu.cn@g; s@//security.debian.org@//mirrors.ustc.edu.cn@g' /etc/apt/sources.list; \
    fi

RUN mkdir -p /opt/playwright-browsers /tmp/chromium /tmp/downloads \
    && rm -f /etc/apt/apt.conf.d/docker-clean

# Keep apt archives outside the image layer so canceled builds can reuse downloads.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends chromium fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# LibreOffice is the slowest install; isolate it so later layers remain reusable.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-writer \
        libreoffice-calc \
        libreoffice-impress \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    python -m pip install --prefer-binary \
        --index-url "${PIP_INDEX_URL}" \
        --timeout "${PIP_TIMEOUT}" \
        --retries "${PIP_RETRIES}" \
        playwright python-docx python-pptx \
    && chown -R 10001:10001 /opt/playwright-browsers /tmp/chromium /tmp/downloads

USER 10001:10001
WORKDIR /workspace
CMD ["sh", "-c", "rm -f /workspace/.agent.sock && exec uvicorn --app-dir /opt/sandbox sandbox_agent:app --uds /workspace/.agent.sock"]
