#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-${HOME}/projects/xhs-auto-publisher}"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
CONTENT_PATH="${1:-${PROJECT_ROOT}/examples/openclaw_business_content.json}"
MODE="${MODE:-publish}"
LOGIN_TIMEOUT="${LOGIN_TIMEOUT:-300}"
DISPLAY_NUM="${DISPLAY_NUM:-99}"

if [ -f "${PROJECT_ROOT}/.env" ]; then
  # shellcheck disable=SC1091
  set -a
  . "${PROJECT_ROOT}/.env"
  set +a
fi

echo "[run] project root: ${PROJECT_ROOT}"
echo "[run] content path: ${CONTENT_PATH}"
echo "[run] mode: ${MODE}"
echo "[run] login timeout: ${LOGIN_TIMEOUT}"

if [ ! -x "${PYTHON_BIN}" ]; then
  echo "[run] python environment not found: ${PYTHON_BIN}" >&2
  exit 1
fi

if [ ! -f "${CONTENT_PATH}" ]; then
  echo "[run] content file not found: ${CONTENT_PATH}" >&2
  exit 1
fi

cd "${PROJECT_ROOT}"

exec xvfb-run \
  --auto-servernum \
  --server-num="${DISPLAY_NUM}" \
  --server-args="-screen 0 1440x1000x24" \
  "${PYTHON_BIN}" \
  "${PROJECT_ROOT}/scripts/publish_xhs.py" \
  --content "${CONTENT_PATH}" \
  --mode "${MODE}" \
  --login-timeout "${LOGIN_TIMEOUT}"
