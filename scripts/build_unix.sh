#!/usr/bin/env sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_DIR"

if [ ! -x ".venv/bin/python" ]; then
    python3 -m venv .venv
fi

.venv/bin/python -m pip install -r requirements-dev.txt
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
rm -rf "$PROJECT_DIR/build" "$PROJECT_DIR/dist"
.venv/bin/python -m PyInstaller \
    --noconfirm --clean --windowed --onedir \
    --name "秋招进程台账" main.py
printf '打包完成：%s\n' "$PROJECT_DIR/dist/秋招进程台账"
