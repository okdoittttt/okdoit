/**
 * Electron 메인 프로세스 진입점.
 *
 * 책임:
 *   1) 사용자 설정(LLM 키)을 OS 보안 저장소에서 읽어 sidecar spawn env 에 머지.
 *   2) Python sidecar (FastAPI) 자식 프로세스를 spawn 한다.
 *      - dev: ``python -m server.main`` (사용자의 venv)
 *      - prod: PyInstaller 로 묶은 ``okdoit-agent`` 실행 파일 (`extraResources` 임베드)
 *   3) sidecar 의 /health 가 200 응답할 때까지 기다린 뒤 BrowserWindow 를 띄운다.
 *   4) 앱 종료 시 sidecar 를 SIGTERM → 일정 시간 후 SIGKILL 로 정리한다.
 *   5) prod 에선 strict CSP 를 응답 헤더로 주입한다(dev 는 Vite HMR 호환을 위해 생략).
 *
 * 동적 포트(v0.2) — OS 가 잡아주는 free port 를 sidecar 와 preload 에 모두 전달.
 *
 * 설정 미완료 흐름(v0.4 UX):
 *   - ``settings.isReady()`` 가 false 면 sidecar 를 띄우지 않고 창만 먼저 띄운다.
 *   - renderer 의 ``SettingsView`` 가 키 입력 → ``okdoit:settings:save`` IPC 호출.
 *   - main 이 settings 저장 + sidecar 처음 spawn + window reload.
 */

import { app, BrowserWindow, ipcMain, session, shell } from "electron";
import { spawn, type ChildProcess } from "node:child_process";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";
import waitOn from "wait-on";

import {
  getSettingsView,
  isReady,
  loadEnvForSidecar,
  saveSettings,
  type SaveSettingsInput,
} from "./settings.js";

// ── 상수 ───────────────────────────────────────────────────────

/** sidecar 헬스체크 대기 최대 시간(ms). 첫 부팅 시 의존성 import 가 느릴 수 있음. */
const SIDECAR_BOOT_TIMEOUT_MS = 30_000;

/** SIGTERM 후 강제 종료(SIGKILL)까지 유예 시간(ms). */
const SIDECAR_KILL_GRACE_MS = 3_000;

/** 메인 윈도우 초기 크기. */
const WINDOW_WIDTH = 1280;
const WINDOW_HEIGHT = 800;

/** 로컬 sidecar 베이스 호스트. 외부 노출 금지. */
const SIDECAR_HOST = "127.0.0.1";

/** PyInstaller 산출물 디렉토리(``extraResources`` 안). */
const SIDECAR_BIN_DIR = "sidecar";

/** PyInstaller 가 만든 실행 파일 이름(``scripts/build_sidecar.sh`` 의 --name 과 동기화). */
const SIDECAR_BIN_NAME = process.platform === "win32" ? "okdoit-agent.exe" : "okdoit-agent";

/** 동봉된 Chromium 위치. ``scripts/build_sidecar.sh`` 가 만든 디렉토리 구조와 동기화. */
const PLAYWRIGHT_BROWSERS_SUBDIR = "playwright-browsers";

/**
 * prod 응답에 부착할 strict CSP. dev 환경(Vite HMR)에서는 절대 사용하지 않는다.
 */
const PROD_CSP =
  "default-src 'self'; " +
  "connect-src 'self' http://127.0.0.1:* ws://127.0.0.1:* http://localhost:* ws://localhost:*; " +
  "img-src 'self' http://127.0.0.1:* data:; " +
  "style-src 'self' 'unsafe-inline'; " +
  "script-src 'self'";

// ── 경로 ───────────────────────────────────────────────────────

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/** 프로젝트 루트(`desktop/` 의 부모 = `okdoit/`). dev 모드에서 `python -m server.main` 의 cwd 가 된다. */
const PROJECT_ROOT = path.resolve(__dirname, "../../..");

// ── 전역 상태 ──────────────────────────────────────────────────

let sidecar: ChildProcess | null = null;
let mainWindow: BrowserWindow | null = null;

// ── 유틸 ──────────────────────────────────────────────────────

async function getFreePort(): Promise<number> {
  return new Promise<number>((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on("error", reject);
    srv.listen(0, SIDECAR_HOST, () => {
      const addr = srv.address();
      if (addr === null || typeof addr === "string") {
        srv.close();
        reject(new Error("free port 주소 가져오기 실패"));
        return;
      }
      const { port } = addr;
      srv.close(() => resolve(port));
    });
  });
}

/**
 * dev / prod 모드별로 sidecar 실행 명령과 인자를 결정한다.
 *
 * 반환되는 ``env`` 는 ``process.env`` + sidecar 동적 포트 + (있다면) 사용자가
 * 저장한 LLM 설정/키를 모두 머지한 결과다.
 */
function resolveSidecarCommand(port: number): {
  command: string;
  args: string[];
  cwd: string;
  env: NodeJS.ProcessEnv;
} {
  const isDev = !app.isPackaged;
  const userEnv = loadEnvForSidecar() ?? {};
  const baseEnv = {
    ...process.env,
    ...userEnv,
    OKDOIT_HOST: SIDECAR_HOST,
    OKDOIT_PORT: String(port),
  };

  if (isDev) {
    const pythonBin = process.env.OKDOIT_PYTHON ?? "python";
    return {
      command: pythonBin,
      args: ["-m", "server.main"],
      cwd: PROJECT_ROOT,
      env: baseEnv,
    };
  }

  // prod — PyInstaller 산출물 + 동봉 Chromium 사용.
  const resourcesPath = process.resourcesPath;
  const sidecarDir = path.join(resourcesPath, SIDECAR_BIN_DIR);
  const sidecarBin = path.join(sidecarDir, SIDECAR_BIN_NAME);
  const browsersPath = path.join(sidecarDir, PLAYWRIGHT_BROWSERS_SUBDIR);
  return {
    command: sidecarBin,
    args: [],
    cwd: sidecarDir,
    env: {
      ...baseEnv,
      PLAYWRIGHT_BROWSERS_PATH: browsersPath,
    },
  };
}

// ── sidecar 라이프사이클 ───────────────────────────────────────

async function startSidecar(port: number): Promise<void> {
  const { command, args, cwd, env } = resolveSidecarCommand(port);

  sidecar = spawn(command, args, {
    cwd,
    env,
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
    resources: [`http-get://${SIDECAR_HOST}:${port}/health`],
    timeout: SIDECAR_BOOT_TIMEOUT_MS,
    interval: 200,
  });
}

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

/**
 * sidecar 를 종료하고 ``exit`` 이벤트가 발생할 때까지 기다린다.
 *
 * 설정 변경 후 새 환경변수로 재시작할 때 이전 인스턴스가 완전히 죽기 전에
 * 새 인스턴스를 띄우면 같은 포트 race 또는 dangling Playwright 프로세스가
 * 생길 수 있어 명시적으로 await 한다.
 */
async function stopSidecarAndWait(): Promise<void> {
  if (!sidecar || sidecar.killed) {
    sidecar = null;
    return;
  }
  const proc = sidecar;
  const exited = new Promise<void>((resolve) => {
    proc.once("exit", () => resolve());
  });
  stopSidecar();
  await exited;
  sidecar = null;
}

/**
 * 동적 포트 할당 + 환경변수 set + sidecar spawn 의 한 묶음.
 *
 * 호출 측이 두 번(부팅 / 설정 저장 후 첫 spawn)에서 사용한다.
 */
async function bootSidecar(): Promise<number> {
  const port = await getFreePort();
  // preload 가 ``process.env.OKDOIT_PORT`` 를 읽어 sidecar URL 을 만든다.
  process.env.OKDOIT_HOST = SIDECAR_HOST;
  process.env.OKDOIT_PORT = String(port);
  console.log(`[main] sidecar 포트: ${port}`);
  await startSidecar(port);
  return port;
}

// ── 보안 (CSP) ────────────────────────────────────────────────

function installCsp(): void {
  if (!app.isPackaged) return;

  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        "Content-Security-Policy": [PROD_CSP],
      },
    });
  });
}

// ── IPC (settings) ────────────────────────────────────────────

/**
 * Renderer ↔ main IPC 핸들러.
 *
 * - ``okdoit:settings:status`` → 활성 프로바이더에 키가 있는지(``isReady``).
 * - ``okdoit:settings:get`` → 평문 키 없이 안전한 표현 반환.
 * - ``okdoit:settings:save`` → 키 저장 + 미부팅 상태였으면 sidecar 처음 띄우고 reload.
 */
function registerIpc(): void {
  ipcMain.handle("okdoit:settings:status", () => ({ ready: isReady() }));

  ipcMain.handle("okdoit:settings:get", () => getSettingsView());

  ipcMain.handle(
    "okdoit:settings:save",
    async (_event, payload: SaveSettingsInput) => {
      saveSettings(payload);

      // 활성 프로바이더 키가 부족하면 sidecar 안 띄우고 SettingsView 유지.
      if (!isReady()) {
        if (sidecar) await stopSidecarAndWait();
        return { ok: true, restarted: false };
      }

      // 첫 입력(spawn) / 변경(restart) 모두 같은 흐름:
      // 기존 sidecar 죽이고, 새 환경변수로 spawn, renderer reload.
      try {
        if (sidecar) await stopSidecarAndWait();
        await bootSidecar();
        mainWindow?.webContents.reload();
        return { ok: true, restarted: true };
      } catch (err) {
        console.error("[main] settings 저장 후 sidecar 재시작 실패:", err);
        return {
          ok: false,
          error: err instanceof Error ? err.message : String(err),
        };
      }
    },
  );
}

// ── 윈도우 ────────────────────────────────────────────────────

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

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url);
    return { action: "deny" };
  });

  const devUrl = process.env.ELECTRON_RENDERER_URL;
  if (devUrl) {
    void mainWindow.loadURL(devUrl);
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    void mainWindow.loadFile(path.join(__dirname, "../renderer/index.html"));
  }
}

// ── 앱 라이프사이클 ────────────────────────────────────────────

void app.whenReady().then(async () => {
  installCsp();
  registerIpc();

  // 설정이 완료된 상태면 바로 sidecar 띄움. 아니면 SettingsView 가 끝나길 기다린다.
  if (isReady()) {
    try {
      await bootSidecar();
    } catch (err) {
      console.error("[main] sidecar 부팅 실패:", err);
      // sidecar 실패해도 창은 띄워서 사용자가 설정을 다시 시도할 수 있게 한다.
    }
  } else {
    console.log("[main] 설정 미완료 — SettingsView 노출 후 사용자 입력 대기");
  }

  createMainWindow();
});

app.on("window-all-closed", () => {
  app.quit();
});

app.on("before-quit", () => {
  stopSidecar();
});
