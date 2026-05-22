#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-${HOME}/projects/xhs-auto-publisher}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "[project] preparing project directories"
mkdir -p "${PROJECT_ROOT}"
mkdir -p "${PROJECT_ROOT}/runtime/browser-profile"
mkdir -p "${PROJECT_ROOT}/runtime/runs"
mkdir -p "${PROJECT_ROOT}/runtime/lobster-notify"

if [ ! -d "${PROJECT_ROOT}/.venv" ]; then
  echo "[project] creating virtual environment"
  "${PYTHON_BIN}" -m venv "${PROJECT_ROOT}/.venv"
fi

echo "[project] installing python dependencies"
"${PROJECT_ROOT}/.venv/bin/pip" install --upgrade pip
"${PROJECT_ROOT}/.venv/bin/pip" install -r "${PROJECT_ROOT}/requirements.txt"

echo "[project] installing playwright chromium into this project environment"
"${PROJECT_ROOT}/.venv/bin/python" -m playwright install chromium

echo "[project] done"
echo "[project] root: ${PROJECT_ROOT}"
