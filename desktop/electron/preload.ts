/**
 * preload 스크립트.
 *
 * Renderer(Chromium) 에 노출할 좁은 API surface 를 정의한다. `contextIsolation: true`
 * 환경에서는 main/renderer 가 서로 다른 컨텍스트라 직접 객체를 공유할 수 없으므로
 * `contextBridge.exposeInMainWorld` 로만 전달한다.
 *
 * 현재는 sidecar 베이스 URL 만 노출한다. v0.2 에서 동적 포트로 바뀌면 이 값을
 * 환경변수에서 읽어오게 변경한다.
 */

import { contextBridge } from "electron";

const SIDECAR_HOST = process.env.OKDOIT_HOST ?? "127.0.0.1";
const SIDECAR_PORT = process.env.OKDOIT_PORT ?? "8765";

/** Renderer 에 노출되는 API 모양. `electron/preload.d.ts` 와 동기화. */
const okdoitApi = {
  sidecarUrl: `http://${SIDECAR_HOST}:${SIDECAR_PORT}`,
  wsUrl: `ws://${SIDECAR_HOST}:${SIDECAR_PORT}`,
  platform: process.platform,
} as const;

contextBridge.exposeInMainWorld("okdoit", okdoitApi);
