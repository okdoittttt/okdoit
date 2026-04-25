/**
 * preload 가 renderer 의 ``window`` 에 주입하는 API 의 타입 정의.
 *
 * 실제 노출은 ``electron/preload.ts`` 가 한다. 이 파일은 React 측에서 ``window.okdoit.*``
 * 를 타입 안전하게 쓰기 위한 ambient declaration 이다.
 */

export {};

declare global {
  interface OkdoitApi {
    /** sidecar 의 HTTP 베이스 URL. 예: ``"http://127.0.0.1:8765"``. */
    readonly sidecarUrl: string;
    /** sidecar 의 WebSocket 베이스 URL. 예: ``"ws://127.0.0.1:8765"``. */
    readonly wsUrl: string;
    /** OS 플랫폼 식별자(``"darwin" | "win32" | "linux"`` 등). */
    readonly platform: NodeJS.Platform;
  }

  interface Window {
    okdoit: OkdoitApi;
  }
}
