/**
 * preload 가 renderer 의 ``window`` 에 주입하는 API 의 타입 정의.
 *
 * 실제 노출은 ``electron/preload.ts`` 가 한다. 이 파일은 React 측에서 ``window.okdoit.*``
 * 를 타입 안전하게 쓰기 위한 ambient declaration 이다.
 */

export {};

declare global {
  interface SaveSettingsInput {
    llmProvider: string;
    llmModel: string;
    /** 환경변수 이름을 키로 한 평문 API 키 맵 (예: ``ANTHROPIC_API_KEY``). */
    apiKeys: Record<string, string>;
    ollamaBaseUrl?: string;
  }

  interface OkdoitSettingsApi {
    /** 활성 프로바이더에 필요한 키가 저장돼 있는지 확인. */
    status: () => Promise<{ ready: boolean }>;
    /** UI 노출용 안전한 표현(평문 키 X). 설정이 없으면 ``null``. */
    get: () => Promise<{
      llmProvider: string;
      llmModel: string;
      hasKey: Record<string, boolean>;
      ollamaBaseUrl: string;
    } | null>;
    /**
     * 설정 저장. 첫 입력이면 main 이 sidecar 를 처음 spawn 하고 page reload.
     * ``restarted: true`` 면 reload 가 곧 발생.
     */
    save: (
      input: SaveSettingsInput,
    ) => Promise<{ ok: boolean; restarted?: boolean; error?: string }>;
  }

  interface OkdoitApi {
    /** sidecar 의 HTTP 베이스 URL. 예: ``"http://127.0.0.1:8765"``. */
    readonly sidecarUrl: string;
    /** sidecar 의 WebSocket 베이스 URL. 예: ``"ws://127.0.0.1:8765"``. */
    readonly wsUrl: string;
    /** OS 플랫폼 식별자(``"darwin" | "win32" | "linux"`` 등). */
    readonly platform: NodeJS.Platform;
    /** 사용자 설정(LLM 프로바이더 + API 키) 관리. */
    readonly settings: OkdoitSettingsApi;
  }

  interface Window {
    okdoit: OkdoitApi;
  }
}
