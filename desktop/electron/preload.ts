/**
 * preload 스크립트.
 *
 * Renderer(Chromium) 에 노출할 좁은 API surface 를 정의한다. ``contextIsolation: true``
 * 환경에서는 main/renderer 가 서로 다른 컨텍스트라 직접 객체를 공유할 수 없으므로
 * ``contextBridge.exposeInMainWorld`` 로만 전달한다.
 *
 * 노출하는 항목:
 *   - sidecar URL / WS URL — preload 가 평가될 때의 ``OKDOIT_PORT`` 를 사용.
 *     설정 저장 후 main 이 ``webContents.reload()`` 를 부르므로 preload 가 다시
 *     평가되고 새 포트가 반영된다.
 *   - settings 관련 IPC 래퍼 — 평문 키는 한 방향(저장)으로만 흐른다.
 */

import { contextBridge, ipcRenderer } from "electron";

const SIDECAR_HOST = process.env.OKDOIT_HOST ?? "127.0.0.1";
const SIDECAR_PORT = process.env.OKDOIT_PORT ?? "8765";

interface SaveSettingsInput {
  llmProvider: string;
  llmModel: string;
  apiKeys: Record<string, string>;
  ollamaBaseUrl?: string;
}

const okdoitApi = {
  sidecarUrl: `http://${SIDECAR_HOST}:${SIDECAR_PORT}`,
  wsUrl: `ws://${SIDECAR_HOST}:${SIDECAR_PORT}`,
  platform: process.platform,
  settings: {
    /** 활성 프로바이더에 필요한 키가 저장돼 있는지. */
    status: (): Promise<{ ready: boolean }> =>
      ipcRenderer.invoke("okdoit:settings:status"),
    /** UI 노출용 안전한 표현. 평문 키는 절대 포함되지 않는다. */
    get: (): Promise<{
      llmProvider: string;
      llmModel: string;
      hasKey: Record<string, boolean>;
      ollamaBaseUrl: string;
    } | null> => ipcRenderer.invoke("okdoit:settings:get"),
    /**
     * 설정 저장. 첫 입력이면 main 이 sidecar 를 처음 spawn 하고 페이지를 reload 한다.
     * 즉 ``true`` 가 돌아오면 곧 페이지 reload 가 발생함을 가정해야 한다.
     */
    save: (
      input: SaveSettingsInput,
    ): Promise<{ ok: boolean; restarted?: boolean; error?: string }> =>
      ipcRenderer.invoke("okdoit:settings:save", input),
  },
} as const;

contextBridge.exposeInMainWorld("okdoit", okdoitApi);
