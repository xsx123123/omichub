# syntax=docker/dockerfile:1.7
# OmicStudio 沙盒基础镜像（cygnusx-sandbox-base:v0.0.2dev）
# 构建：docker build -t cygnusx-sandbox-base:v0.0.2dev -f deploy/studio/base.Dockerfile deploy/studio
#
# 设计（架构设计 §6.1）：
# - python:3.12-slim + 数据分析栈（pandas/numpy/matplotlib/plotly/seaborn
#   + scikit-learn/scipy/statsmodels + openpyxl/pyarrow）
# - 内置 sandbox-agent 小服务（/exec /files/*），宿主经工作区 Unix Socket 直连交互
# - 统一非 root 用户（uid 10001），/workspace 为唯一可写工作区
FROM python:3.12-slim

ARG SANDBOX_UID=10001
ARG SANDBOX_GID=10001
ARG SANDBOX_GROUP=cygnusx-sandbox
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ARG PIP_TIMEOUT=60
ARG PIP_RETRIES=5

LABEL maintainer="CygnusX"
LABEL description="OmicStudio sandbox base image (data science stack + sandbox-agent)"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLBACKEND=Agg \
    SANDBOX_WORKSPACE=/workspace

# 非 root 运行用户 + 工作区目录（宿主编排侧仍必须为 bind mount 放权）
RUN groupadd --gid "$SANDBOX_GID" "$SANDBOX_GROUP" \
    && useradd --create-home --uid "$SANDBOX_UID" --gid "$SANDBOX_GROUP" sandbox \
    && mkdir -p /workspace/.logs \
    && chown -R "$SANDBOX_UID:$SANDBOX_GID" /workspace

# 单一、可覆盖的 PyPI 镜像；失败时由 build.sh 重试整条镜像链。
RUN printf '%s\n' \
      '[global]' \
      "index-url = ${PIP_INDEX_URL}" \
      "timeout = ${PIP_TIMEOUT}" \
      "retries = ${PIP_RETRIES}" \
      'disable-pip-version-check = true' \
      > /etc/pip.conf

# 构建期切换中科大 apt 源，加速 apt-get（兼容 debian.sources 与旧版 sources.list）
RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's@//deb.debian.org@//mirrors.ustc.edu.cn@g; s@//security.debian.org@//mirrors.ustc.edu.cn@g' /etc/apt/sources.list.d/debian.sources; \
    else \
        sed -i 's@//deb.debian.org@//mirrors.ustc.edu.cn@g; s@//security.debian.org@//mirrors.ustc.edu.cn@g' /etc/apt/sources.list; \
    fi

# sandbox-agent 依赖（最小集）+ 数据分析栈
COPY requirements-agent.txt /tmp/requirements-agent.txt
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    python -m pip install \
        --index-url "${PIP_INDEX_URL}" \
        --prefer-binary \
        --timeout "${PIP_TIMEOUT}" \
        --retries "${PIP_RETRIES}" \
        -r /tmp/requirements-agent.txt \
        pandas \
        numpy \
        matplotlib \
        plotly \
        seaborn \
        scikit-learn \
        scipy \
        statsmodels \
        openpyxl \
        pyarrow \
    && rm -f /tmp/requirements-agent.txt

# 烘焙 sandbox-agent 服务
COPY sandbox_agent.py /opt/sandbox/sandbox_agent.py

# sitecustomize.py：Python 启动时自动注入 show_plotly 图表回传 helper，
# 与聊天轻量沙盒（deploy/sandbox/sitecustomize.py）同一 %%PLOTLY%% 标记协议
COPY sitecustomize.py /usr/local/lib/python3.12/site-packages/sitecustomize.py

USER 10001:10001
WORKDIR /workspace
CMD ["sh", "-c", "rm -f /workspace/.agent.sock && exec uvicorn --app-dir /opt/sandbox sandbox_agent:app --uds /workspace/.agent.sock"]
