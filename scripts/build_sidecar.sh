#!/usr/bin/env bash
# sidecar (server.main) 를 PyInstaller 로 단일 디렉토리 산출물로 묶는다.
#
# 산출물 구조:
#   dist/okdoit-agent/
#     ├── okdoit-agent           # 실행 파일
#     ├── _internal/             # PyInstaller 가 모은 라이브러리들
#     └── playwright-browsers/   # Chromium 동봉 (PLAYWRIGHT_BROWSERS_PATH)
#
# 그 다음 electron-builder 가 이 디렉토리 통째로 ``desktop/resources/sidecar/`` 에 임베드한다.
#
# 알려진 함정:
#   - langchain_*, langgraph 는 동적 import 가 많아 ``--collect-all`` 필수
#   - uvicorn 의 워커 프로토콜 모듈은 ``--hidden-import`` 로 명시
#   - Playwright Chromium 은 PyInstaller 가 자동으로 못 찾음 → 별도 디렉토리에 install 후 동봉

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DIST_DIR="${ROOT}/dist"
APP_NAME="okdoit-agent"
BROWSERS_DIR="${DIST_DIR}/${APP_NAME}/playwright-browsers"

echo "[build_sidecar] 1/3 PyInstaller 로 sidecar 묶기"
pyinstaller \
    --name "${APP_NAME}" \
    --onedir \
    --noconfirm \
    --clean \
    --distpath "${DIST_DIR}" \
    --add-data "prompt:prompt" \
    --collect-submodules server.internal \
    --collect-all langchain_core \
    --collect-all langgraph \
    --collect-all langchain_anthropic \
    --collect-all langchain_google_genai \
    --collect-all langchain_ollama \
    --collect-all playwright \
    --collect-all playwright_stealth \
    --hidden-import uvicorn.logging \
    --hidden-import uvicorn.loops \
    --hidden-import uvicorn.loops.auto \
    --hidden-import uvicorn.protocols \
    --hidden-import uvicorn.protocols.http \
    --hidden-import uvicorn.protocols.http.h11_impl \
    --hidden-import uvicorn.protocols.websockets \
    --hidden-import uvicorn.protocols.websockets.websockets_impl \
    --hidden-import uvicorn.lifespan \
    --hidden-import uvicorn.lifespan.on \
    server/main.py

echo "[build_sidecar] 2/3 Playwright Chromium 을 동봉 디렉토리에 install"
mkdir -p "${BROWSERS_DIR}"
PLAYWRIGHT_BROWSERS_PATH="${BROWSERS_DIR}" python -m playwright install chromium

echo "[build_sidecar] 3/3 검증 — 산출물 단독 실행"
"${DIST_DIR}/${APP_NAME}/${APP_NAME}" --help >/dev/null 2>&1 || {
    echo "[build_sidecar] 경고: 산출물 단독 실행 검증 실패. 직접 ${DIST_DIR}/${APP_NAME}/${APP_NAME} 실행해 점검하세요."
}

echo ""
echo "[build_sidecar] 완료"
echo "  산출물: ${DIST_DIR}/${APP_NAME}/"
echo "  크기: $(du -sh "${DIST_DIR}/${APP_NAME}" | cut -f1)"
echo ""
echo "다음 단계:"
echo "  cd desktop && npm run build:dmg     # macOS dmg"
echo "  cd desktop && npm run build:win     # Windows exe"
