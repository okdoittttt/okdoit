/**
 * Electron 메인 프로세스 진입점.
 *
 * 책임:
 *   1) Python sidecar (FastAPI) 자식 프로세스를 spawn 한다.
 *   2) sidecar 의 /health 가 200 응답할 때까지 기다린 뒤 BrowserWindow 를 띄운다.
 *   3) 앱 종료 시 sidecar 를 SIGTERM → 일정 시간 후 SIGKILL 로 정리한다.
 *
 * v0.1 은 dev 모드만 지원한다(`python -m server.main` 직접 실행).
 * v0.4 에서 PyInstaller 산출물로 prod 분기를 추가할 예정 — `.plan/05-packaging-distribution.md`.
 */

import { app, BrowserWindow, shell } from "electron";
import { spawn, type ChildProcess } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import waitOn from "wait-on";

// ── 상수 ───────────────────────────────────────────────────────

/** sidecar 가 바인딩할 포트. v0.2 에서 동적 포트로 교체 예정. */
const SIDECAR_PORT = 8765;

/** sidecar 헬스체크 대기 최대 시간(ms). 첫 부팅 시 의존성 import 가 느릴 수 있음. */
const SIDECAR_BOOT_TIMEOUT_MS = 30_000;

/** SIGTERM 후 강제 종료(SIGKILL)까지 유예 시간(ms). */
const SIDECAR_KILL_GRACE_MS = 3_000;

/** 메인 윈도우 초기 크기. */
const WINDOW_WIDTH = 1280;
const WINDOW_HEIGHT = 800;

/** 로컬 sidecar 베이스 URL. */
const SIDECAR_HOST = "127.0.0.1";

// ── 경로 ───────────────────────────────────────────────────────

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/** 프로젝트 루트(`desktop/` 의 부모 = `okdoit/`). dev 모드에서 `python -m server.main` 의 cwd 가 된다. */
const PROJECT_ROOT = path.resolve(__dirname, "../../..");

// ── 전역 상태 ──────────────────────────────────────────────────

let sidecar: ChildProcess | null = null;
let mainWindow: BrowserWindow | null = null;

// ── sidecar 라이프사이클 ───────────────────────────────────────

/**
 * Python sidecar 를 spawn 하고 /health 가 응답할 때까지 기다린다.
 *
 * dev 모드: 시스템 `python` 으로 `python -m server.main` 실행.
 * prod 모드(미구현): PyInstaller 로 묶은 단일 실행 파일을 띄울 예정.
 */
async function startSidecar(): Promise<void> {
  const isDev = !app.isPackaged;

  if (!isDev) {
    throw new Error(
      "프로덕션 빌드는 v0.4 에서 지원 예정입니다 (PyInstaller 산출물 필요)."
    );
  }

  const pythonBin = process.env.OKDOIT_PYTHON ?? "python";

  sidecar = spawn(pythonBin, ["-m", "server.main"], {
    cwd: PROJECT_ROOT,
    env: {
      ...process.env,
      OKDOIT_HOST: SIDECAR_HOST,
      OKDOIT_PORT: String(SIDECAR_PORT),
    },
    stdio: ["ignore", "pipe", "pipe"],
  });

  sidecar.stdout?.on("data", (chunk: Buffer) => {
    process.stdout.write(`[sidecar] ${chunk.toString()}`);
  });
  sidecar.stderr?.on("data", (chunk: Buffer) => {
    process.stderr.write(`[sidecar] ${chunk.toString()}`);
  });
  sidecar.on("exit", (code, signal) => {
    console.log(`[sidecar] exited code=${code} signal=${signal}`);
    sidecar = null;
  });

  await waitOn({
    resources: [`http-get://${SIDECAR_HOST}:${SIDECAR_PORT}/health`],
    timeout: SIDECAR_BOOT_TIMEOUT_MS,
    interval: 200,
  });
}

/**
 * sidecar 에 SIGTERM 을 보내고, 일정 시간 안에 종료되지 않으면 SIGKILL 한다.
 *
 * `before-quit` 핸들러에서 호출된다. 이미 종료됐으면 no-op.
 */
function stopSidecar(): void {
  if (!sidecar || sidecar.killed) return;

  sidecar.kill("SIGTERM");
  setTimeout(() => {
    if (sidecar && !sidecar.killed) {
      console.warn("[sidecar] SIGTERM 후에도 살아있어 SIGKILL 합니다.");
      sidecar.kill("SIGKILL");
    }
  }, SIDECAR_KILL_GRACE_MS);
}

// ── 윈도우 ────────────────────────────────────────────────────

/**
 * 메인 BrowserWindow 를 만들어 dev 서버 또는 빌드된 renderer 를 로드한다.
 *
 * dev 모드: electron-vite 가 띄운 Vite dev 서버 URL(`ELECTRON_RENDERER_URL`) 을 로드.
 * prod 모드: 빌드된 `out/renderer/index.html` 을 로드.
 */
function createMainWindow(): void {
  mainWindow = new BrowserWindow({
    width: WINDOW_WIDTH,
    height: WINDOW_HEIGHT,
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "../preload/index.mjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.on("ready-to-show", () => mainWindow?.show());

  // 외부 링크는 OS 기본 브라우저로 연다.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url);
    return { action: "deny" };
  });

  const devUrl = process.env.ELECTRON_RENDERER_URL;
  if (devUrl) {
    void mainWindow.loadURL(devUrl);
  } else {
    void mainWindow.loadFile(path.join(__dirname, "../renderer/index.html"));
  }
}

// ── 앱 라이프사이클 ────────────────────────────────────────────

void app.whenReady().then(async () => {
  try {
    await startSidecar();
  } catch (err) {
    console.error("[main] sidecar 부팅 실패:", err);
    app.quit();
    return;
  }
  createMainWindow();
});

app.on("window-all-closed", () => {
  // macOS 도 포함해 모든 창이 닫히면 종료한다(데스크탑 앱 기준 단순화).
  app.quit();
});

app.on("before-quit", () => {
  stopSidecar();
});
