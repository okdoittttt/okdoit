/**
 * 사용자 설정 저장소 — LLM 프로바이더 + API 키.
 *
 * 보안:
 *   - Electron 의 ``safeStorage`` API 로 OS 보안 저장소(macOS Keychain, Windows
 *     DPAPI, Linux libsecret)에 위임해 평문 키가 디스크에 노출되지 않게 한다.
 *   - 저장 위치: ``app.getPath("userData")/settings.json`` (사용자 한정 권한).
 *
 * 흐름:
 *   - ``saveSettings(...)`` — 평문 입력을 받아 키만 암호화해서 파일에 기록.
 *   - ``loadDecrypted()`` — sidecar spawn 시 환경변수로 전달할 평문 키 묶음 반환.
 *   - ``getSettingsView()`` — UI 노출용. 평문 키는 절대 돌려주지 않고 존재 여부만.
 *   - ``isReady()`` — 활성 프로바이더에 필요한 키가 있으면 true.
 */

import { app, safeStorage } from "electron";
import fs from "node:fs";
import path from "node:path";

// ── 상수 ───────────────────────────────────────────────────────

const SETTINGS_FILENAME = "settings.json";

/** 지원 LLM 프로바이더. ``server.internal.config`` 의 ``LLM_PROVIDER`` 와 동기화. */
export type LlmProvider = "anthropic" | "gemini" | "openai" | "ollama";

/** 프로바이더별 필수 API 키 환경변수 이름. ``null`` 은 키 불필요. */
const REQUIRED_KEY_ENV: Record<LlmProvider, string | null> = {
  anthropic: "ANTHROPIC_API_KEY",
  gemini: "GOOGLE_API_KEY",
  openai: "OPENAI_API_KEY",
  ollama: null,
};

// ── 직렬화 형태 ────────────────────────────────────────────────

interface PersistedSettings {
  llmProvider: LlmProvider;
  llmModel: string;
  /** 키는 환경변수 이름(``ANTHROPIC_API_KEY`` 등), 값은 base64 로 인코딩한 암호문. */
  encryptedKeys: Record<string, string>;
  ollamaBaseUrl?: string;
}

/** Renderer 에 노출하는 안전한 표현. 평문 키는 절대 포함하지 않는다. */
export interface SettingsView {
  llmProvider: LlmProvider;
  llmModel: string;
  /** 각 환경변수에 대해 키가 저장돼 있는지 여부만. */
  hasKey: Record<string, boolean>;
  ollamaBaseUrl: string;
}

/** ``saveSettings`` 입력 — 평문 키를 받는다(IPC 경로 외에는 노출 X). */
export interface SaveSettingsInput {
  llmProvider: LlmProvider;
  llmModel: string;
  apiKeys: Record<string, string>;
  ollamaBaseUrl?: string;
}

// ── 파일 입출력 ────────────────────────────────────────────────

function settingsPath(): string {
  return path.join(app.getPath("userData"), SETTINGS_FILENAME);
}

function loadRaw(): PersistedSettings | null {
  try {
    const raw = fs.readFileSync(settingsPath(), "utf-8");
    return JSON.parse(raw) as PersistedSettings;
  } catch {
    return null;
  }
}

function saveRaw(data: PersistedSettings): void {
  const filePath = settingsPath();
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), { mode: 0o600 });
}

// ── 암복호화 ──────────────────────────────────────────────────

function ensureEncryptionAvailable(): void {
  if (!safeStorage.isEncryptionAvailable()) {
    throw new Error(
      "OS 보안 저장소를 사용할 수 없습니다. 설정 저장이 불가능합니다.",
    );
  }
}

function encryptKey(plain: string): string {
  ensureEncryptionAvailable();
  return safeStorage.encryptString(plain).toString("base64");
}

function decryptKey(encoded: string): string {
  ensureEncryptionAvailable();
  return safeStorage.decryptString(Buffer.from(encoded, "base64"));
}

// ── 외부 API ──────────────────────────────────────────────────

/**
 * 활성 프로바이더에 필요한 키가 저장돼 있는지 확인한다.
 *
 * Returns:
 *   설정 파일이 있고, 활성 프로바이더의 필수 키도 채워져 있으면 ``true``.
 */
export function isReady(): boolean {
  const data = loadRaw();
  if (!data) return false;
  const need = REQUIRED_KEY_ENV[data.llmProvider];
  if (need === null) return true; // ollama 등 키 불필요
  if (need === undefined) return false; // 알 수 없는 프로바이더
  return Boolean(data.encryptedKeys?.[need]);
}

/**
 * 설정을 안전하게 저장한다(키는 암호화).
 *
 * Args:
 *   input: 평문 키 + 프로바이더/모델 정보. ``apiKeys`` 는 환경변수 이름을 키로
 *     사용한다(``"ANTHROPIC_API_KEY"`` 등). 빈 문자열 값은 저장하지 않는다.
 */
export function saveSettings(input: SaveSettingsInput): void {
  const encryptedKeys: Record<string, string> = {};
  for (const [envName, value] of Object.entries(input.apiKeys)) {
    if (value && value.trim().length > 0) {
      encryptedKeys[envName] = encryptKey(value);
    }
  }
  const data: PersistedSettings = {
    llmProvider: input.llmProvider,
    llmModel: input.llmModel,
    encryptedKeys,
  };
  if (input.ollamaBaseUrl) data.ollamaBaseUrl = input.ollamaBaseUrl;
  saveRaw(data);
}

/**
 * sidecar spawn 시 환경변수로 전달할 평문 묶음을 반환한다.
 *
 * Returns:
 *   설정이 없으면 ``null``. 있으면 ``{LLM_PROVIDER, LLM_MODEL, OLLAMA_BASE_URL?,
 *   ANTHROPIC_API_KEY?, GOOGLE_API_KEY?, OPENAI_API_KEY?}`` 형태의 환경변수 dict.
 */
export function loadEnvForSidecar(): Record<string, string> | null {
  const data = loadRaw();
  if (!data) return null;

  const env: Record<string, string> = {
    LLM_PROVIDER: data.llmProvider,
    LLM_MODEL: data.llmModel,
  };
  if (data.ollamaBaseUrl) env.OLLAMA_BASE_URL = data.ollamaBaseUrl;

  for (const [envName, encoded] of Object.entries(data.encryptedKeys ?? {})) {
    try {
      env[envName] = decryptKey(encoded);
    } catch (err) {
      console.error(`[settings] 복호화 실패 ${envName}:`, err);
    }
  }
  return env;
}

/**
 * Renderer 에 노출할 안전한 설정 표현(평문 키 X).
 */
export function getSettingsView(): SettingsView | null {
  const data = loadRaw();
  if (!data) return null;
  const hasKey: Record<string, boolean> = {};
  for (const [envName, value] of Object.entries(data.encryptedKeys ?? {})) {
    hasKey[envName] = Boolean(value);
  }
  return {
    llmProvider: data.llmProvider,
    llmModel: data.llmModel,
    hasKey,
    ollamaBaseUrl: data.ollamaBaseUrl ?? "",
  };
}

export { REQUIRED_KEY_ENV };
