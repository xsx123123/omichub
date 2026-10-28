#!/usr/bin/env bash
# 构建 OmicStudio 沙盒镜像：base -> bio -> browser-office
# 可覆盖 PIP_INDEX_URL / PIP_FALLBACK_INDEX_URL / PIP_TIMEOUT / PIP_RETRIES。
# 每层构建日志保存在 STUDIO_BUILD_LOG_DIR（默认 logs/studio-build）。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAG="${CYGNUSX_IMAGE_TAG:-v0.0.2dev}"
SANDBOX_UID="${SANDBOX_UID:-10001}"
SANDBOX_GID="${SANDBOX_GID:-10001}"
SANDBOX_GROUP="${SANDBOX_GROUP:-cygnusx-sandbox}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}"
# 空字符串显式禁用回退；每次尝试整条链只使用一个源，不混用 extra-index-url。
PIP_FALLBACK_INDEX_URL="${PIP_FALLBACK_INDEX_URL-https://pypi.tuna.tsinghua.edu.cn/simple/}"
PIP_TIMEOUT="${PIP_TIMEOUT:-60}"
PIP_RETRIES="${PIP_RETRIES:-5}"
BUILD_LOG_DIR="${STUDIO_BUILD_LOG_DIR:-${SCRIPT_DIR}/../../logs/studio-build}"
LAST_FAILED_LOG=''
mkdir -p "${BUILD_LOG_DIR}"

COMMON_BUILD_ARGS=(
  --build-arg "SANDBOX_UID=${SANDBOX_UID}"
  --build-arg "SANDBOX_GID=${SANDBOX_GID}"
  --build-arg "SANDBOX_GROUP=${SANDBOX_GROUP}"
  --build-arg "PIP_TIMEOUT=${PIP_TIMEOUT}"
  --build-arg "PIP_RETRIES=${PIP_RETRIES}"
)

build_image() {
  local stage="$1" index_url="$2" log_file status
  shift 2
  log_file="$(mktemp "${BUILD_LOG_DIR}/$(date +%Y%m%dT%H%M%S)-${stage}.XXXXXX.log")" || return "$?"
  echo "==> 构建 cygnusx-sandbox-${stage}:${TAG}；日志：${log_file}"
  if docker build --progress=plain -t "cygnusx-sandbox-${stage}:${TAG}" \
      "${COMMON_BUILD_ARGS[@]}" --build-arg "PIP_INDEX_URL=${index_url}" "$@" \
      -f "${SCRIPT_DIR}/${stage}.Dockerfile" "${SCRIPT_DIR}" 2>&1 | tee "${log_file}"; then
    return 0
  else
    status=$?
    LAST_FAILED_LOG="${log_file}"
    return "${status}"
  fi
}

build_images() {
  local index_url="$1"
  build_image base "${index_url}" || return "$?"
  build_image bio "${index_url}" \
    --build-arg "CYGNUSX_IMAGE_TAG=${TAG}" \
    || return "$?"
  build_image browser-office "${index_url}" \
    --build-arg "CYGNUSX_IMAGE_TAG=${TAG}" \
    || return "$?"
}

is_pip_download_failure() {
  # BuildKit frontend/daemon、APT、chown 和依赖冲突不应触发换源。
  grep -Eq 'ERROR: process .*python -m pip install.*exit code:' "$1" \
    && grep -Eq 'ERROR: (THESE PACKAGES DO NOT MATCH|HTTP error|Could not fetch URL)|ReadTimeoutError|ConnectTimeout|ConnectionError|SSLError|Max retries exceeded|Temporary failure in name resolution|Network is unreachable' "$1"
}

echo "==> 使用主 PyPI 源构建 Studio 镜像链"
if build_images "${PIP_INDEX_URL}"; then
  :
else
  build_status=$?
  echo "==> 首个失败日志：${LAST_FAILED_LOG}" >&2
  if ! is_pip_download_failure "${LAST_FAILED_LOG}"; then
    echo "==> 非 pip 下载/哈希错误，保持源不变；请按首个失败日志排查 Docker/BuildKit、APT 或依赖错误" >&2
    exit "${build_status}"
  fi
  if [[ -z "${PIP_FALLBACK_INDEX_URL}" || "${PIP_FALLBACK_INDEX_URL}" == "${PIP_INDEX_URL}" ]]; then
    exit "${build_status}"
  fi
  echo "==> pip 下载/哈希失败；显式切换 PIP_FALLBACK_INDEX_URL，从 base 重试整条镜像链" >&2
  if build_images "${PIP_FALLBACK_INDEX_URL}"; then
    :
  else
    build_status=$?
    echo "==> 备用源构建也失败；日志：${LAST_FAILED_LOG}；首个失败日志仍保留" >&2
    exit "${build_status}"
  fi
fi

echo "==> 完成：cygnusx-sandbox-base:${TAG} / cygnusx-sandbox-bio:${TAG} / cygnusx-sandbox-browser-office:${TAG}"
