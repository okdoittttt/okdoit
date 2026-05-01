/**
 * 사용자 설정(LLM 프로바이더 + API 키) renderer 측 헬퍼.
 *
 * 실제 IPC 는 ``window.okdoit.settings`` 가 노출(``electron/preload.ts``).
 * 이 파일은 (a) 도메인 상수(프로바이더 메타데이터)와 (b) 얇은 타입 래퍼만 제공.
 */

export type LlmProvider = "anthropic" | "gemini" | "openai" | "ollama";

export interface ProviderMeta {
  /** 화면에 노출할 한국어 이름. */
  label: string;
  /** 필수 API 키의 환경변수 이름. ``null`` 이면 키 불필요(ollama). */
  apiKeyEnv: string | null;
  /** 기본 모델 placeholder. */
  defaultModel: string;
  /** API 키 발급 안내 URL. ollama 는 null. */
  apiKeyHelpUrl: string | null;
}

export const PROVIDERS: Record<LlmProvider, ProviderMeta> = {
  anthropic: {
    label: "Anthropic Claude",
    apiKeyEnv: "ANTHROPIC_API_KEY",
    defaultModel: "claude-sonnet-4-6",
    apiKeyHelpUrl: "https://console.anthropic.com/settings/keys",
  },
  gemini: {
    label: "Google Gemini",
    apiKeyEnv: "GOOGLE_API_KEY",
    defaultModel: "gemini-2.0-flash",
    apiKeyHelpUrl: "https://aistudio.google.com/apikey",
  },
  openai: {
    label: "OpenAI",
    apiKeyEnv: "OPENAI_API_KEY",
    defaultModel: "gpt-4o-mini",
    apiKeyHelpUrl: "https://platform.openai.com/api-keys",
  },
  ollama: {
    label: "Ollama (로컬)",
    apiKeyEnv: null,
    defaultModel: "llama3.1:8b",
    apiKeyHelpUrl: null,
  },
};

export const PROVIDER_ORDER: LlmProvider[] = ["anthropic", "gemini", "openai", "ollama"];
