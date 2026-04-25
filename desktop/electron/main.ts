/**
 * Electron 메인 프로세스 진입점.
 *
 * 책임:
 *   1) Python sidecar (FastAPI) 자식 프로세스를 spawn 한다.
 *      - dev: ``python -m server.main`` (사용자의 venv)
 *      - prod: PyInstaller 로 묶은 ``okdoit-agent`` 실행 파일 (`extraResources` 임베드)
 *   2) sidecar 의 /health 가 200 응답할 때까지 기다린 뒤 BrowserWindow 를 띄운다.
 *   3) 앱 종료 시 sidecar 를 SIGTERM → 일정 시간 후 SIGKILL 로 정리한다.
 *   4) prod 에선 strict CSP 를 응답 헤더로 주입한다(dev 는 Vite HMR 호환을 위해 생략).
 *
 * 동적 포트(v0.2) — OS 가 잡아주는 free port 를 sidecar 와 preload 에 모두 전달.
 */

import { app, BrowserWindow, session, shell } from "electron";
import { spawn, type ChildProcess } from "node:child_process";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";
import waitOn from "wait-on";

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
 *
 * 정책:
 *   - default: 'self' 만 (앱 자체 자원)
 *   - connect: localhost / 127.0.0.1 만 (sidecar HTTP + WS)
 *   - img: 'self' + 정적 라우트 + data: (스크린샷 갤러리에 base64 이미지가 들어올 때 대비)
 *   - script/style: 'self' 만 (Vite 가 빌드한 번들)
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

/**
 * OS 가 자동 할당한 free port 를 잡아 그 번호를 돌려주고 즉시 닫는다.
 *
 * 잡은 후 닫고 spawn 하기까지 짧은 race 가 존재하지만, 로컬호스트 + 즉시 사용
 * 패턴에서는 실제로 충돌이 거의 없다. v0.5 이후 필요하면 retry 로직 추가.
 */
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
 * Returns:
 *   ``{ command, args, cwd, env }`` — ``spawn`` 에 그대로 넘길 수 있는 형태.
 */
function resolveSidecarCommand(port: number): {
  command: string;
  args: string[];
  cwd: string;
  env: NodeJS.ProcessEnv;
} {
  const isDev = !app.isPackaged;
  const baseEnv = {
    ...process.env,
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

/**
 * Python sidecar 를 spawn 하고 /health 가 응답할 때까지 기다린다.
 *
 * Args:
 *   port: sidecar 가 바인딩할 포트. ``getFreePort()`` 로 잡은 값.
 */
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

// ── 보안 (CSP) ────────────────────────────────────────────────

/**
 * prod 모드에서 모든 응답에 strict CSP 헤더를 부착한다.
 *
 * dev 모드에서는 Vite HMR 의 inline script + ws://localhost:5173 을 깨므로 호출하지 않는다.
 */
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
    // dev 모드: 디버깅 편의를 위해 DevTools 자동 오픈(detached).
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    void mainWindow.loadFile(path.join(__dirname, "../renderer/index.html"));
  }
}

// ── 앱 라이프사이클 ────────────────────────────────────────────

void app.whenReady().then(async () => {
  try {
    installCsp();

    const port = await getFreePort();
    // preload 가 ``process.env.OKDOIT_PORT`` 를 읽어 sidecar URL 을 만든다.
    process.env.OKDOIT_HOST = SIDECAR_HOST;
    process.env.OKDOIT_PORT = String(port);
    console.log(`[main] sidecar 포트: ${port}`);

    await startSidecar(port);
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
