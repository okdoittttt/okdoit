/**
 * SettingsModal / SettingsView 가 공유하는 본문(폼).
 *
 * 책임:
 *   - ``window.okdoit.settings.get`` 로 기존 값 로딩.
 *   - LLM 프로바이더 그리드 + 모델 + API 키 + Ollama URL 입력 관리.
 *   - 저장 시 ``window.okdoit.settings.save`` 호출. 결과를 콜백으로 전달.
 *
 * 헤드리스 토글은 현재 backend 가 설정으로 받지 않으므로(작업 단위 옵션이므로)
 * 여기서는 노출하지 않는다.
 */

import { useEffect, useState, type CSSProperties } from "react";
import { FONT_MONO, TOKENS } from "@/styles/tokens";
import { PROVIDERS, PROVIDER_ORDER, type LlmProvider } from "@/lib/settings";
import { Field, fieldStyle } from "./Field";

interface Props {
  /** 첫 실행 폼인지(닫기 버튼 / 안내 문구가 달라짐). */
  variant: "first-run" | "edit";
  /** 저장 후(또는 변경 없이 닫을 때) 호출. ``edit`` 일 때만 의미가 있다. */
  onClose?: () => void;
}

interface SubmitResult {
  ok: boolean;
  restarted?: boolean;
  error?: string;
}

const DEFAULT_OLLAMA_URL = "http://localhost:11434";

export function SettingsForm({ variant, onClose }: Props) {
  const [provider, setProvider] = useState<LlmProvider>("anthropic");
  const [model, setModel] = useState<string>(PROVIDERS.anthropic.defaultModel);
  const [apiKey, setApiKey] = useState<string>("");
  const [showKey, setShowKey] = useState<boolean>(false);
  const [ollamaUrl, setOllamaUrl] = useState<string>(DEFAULT_OLLAMA_URL);
  const [hasKeyAlready, setHasKeyAlready] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void window.okdoit.settings.get().then((data) => {
      if (!data) return;
      setProvider(data.llmProvider as LlmProvider);
      setModel(data.llmModel);
      const envName = PROVIDERS[data.llmProvider as LlmProvider].apiKeyEnv;
      if (envName) setHasKeyAlready(Boolean(data.hasKey[envName]));
      if (data.ollamaBaseUrl) setOllamaUrl(data.ollamaBaseUrl);
    });
  }, []);

  function handleProviderChange(next: LlmProvider): void {
    setProvider(next);
    setModel(PROVIDERS[next].defaultModel);
    setApiKey("");
    setHasKeyAlready(false);
  }

  const meta = PROVIDERS[provider];
  const needsApiKey = meta.apiKeyEnv !== null;
  const canSubmit =
    !submitting &&
    model.trim().length > 0 &&
    (!needsApiKey || apiKey.trim().length > 0 || hasKeyAlready);

  async function submit(): Promise<SubmitResult> {
    setSubmitting(true);
    setError(null);
    try {
      const apiKeys: Record<string, string> = {};
      if (needsApiKey && apiKey.trim().length > 0 && meta.apiKeyEnv) {
        apiKeys[meta.apiKeyEnv] = apiKey.trim();
      }
      const result = await window.okdoit.settings.save({
        llmProvider: provider,
        llmModel: model.trim(),
        apiKeys,
        ollamaBaseUrl: provider === "ollama" ? ollamaUrl.trim() : undefined,
      });
      if (!result.ok) {
        setError(result.error ?? "Save failed");
        return result;
      }
      if (!result.restarted && onClose) onClose();
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      return { ok: false, error: message };
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 18,
      }}
    >
      <Field label="LLM Provider">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr 1fr",
            gap: 6,
          }}
        >
          {PROVIDER_ORDER.map((p) => (
            <ProviderBtn
              key={p}
              label={PROVIDERS[p].label}
              active={provider === p}
              onClick={() => handleProviderChange(p)}
            />
          ))}
        </div>
      </Field>

      <Field label="Model">
        <input
          type="text"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          placeholder={meta.defaultModel}
          style={fieldStyle}
        />
      </Field>

      {needsApiKey && (
        <Field
          label={`API Key (${meta.apiKeyEnv ?? ""})`}
          hint={
            hasKeyAlready
              ? "Stored locally. Leave blank to keep the current value."
              : "Stored encrypted in your OS keychain — never sent to okdoit servers."
          }
        >
          <div style={{ position: "relative" }}>
            <input
              type={showKey ? "text" : "password"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={hasKeyAlready ? "•••• stored ••••" : "sk-..."}
              style={{
                ...fieldStyle,
                paddingRight: 64,
                fontFamily: FONT_MONO,
              }}
            />
            <button
              type="button"
              onClick={() => setShowKey((v) => !v)}
              style={{
                position: "absolute",
                right: 6,
                top: 6,
                height: 22,
                padding: "0 8px",
                background: "transparent",
                border: 0,
                color: TOKENS.textDim,
                fontSize: 11,
                fontFamily: "inherit",
                cursor: "pointer",
                borderRadius: 4,
              }}
            >
              {showKey ? "Hide" : "Show"}
            </button>
          </div>
          {meta.apiKeyHelpUrl && (
            <a
              href={meta.apiKeyHelpUrl}
              target="_blank"
              rel="noreferrer"
              style={{
                fontSize: 11,
                color: TOKENS.accent,
                textDecoration: "none",
              }}
            >
              Get a key →
            </a>
          )}
        </Field>
      )}

      {provider === "ollama" && (
        <Field
          label="Ollama Base URL"
          hint="Local Ollama server. No API key needed."
        >
          <input
            type="text"
            value={ollamaUrl}
            onChange={(e) => setOllamaUrl(e.target.value)}
            placeholder={DEFAULT_OLLAMA_URL}
            style={fieldStyle}
          />
        </Field>
      )}

      {error && <ErrorBanner message={error} />}

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginTop: 4,
        }}
      >
        <span style={{ flex: 1 }} />
        {variant === "edit" && onClose && (
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            style={cancelBtnStyle(submitting)}
          >
            Cancel
          </button>
        )}
        <button
          type="button"
          onClick={() => void submit()}
          disabled={!canSubmit}
          style={saveBtnStyle(canSubmit)}
        >
          {submitting
            ? "Saving…"
            : variant === "first-run"
              ? "Save & Launch"
              : "Save"}
        </button>
      </div>
    </div>
  );
}

// ── 내부 partial ────────────────────────────────────────────────

function ProviderBtn({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        height: 34,
        background: active ? `${TOKENS.accent}1F` : TOKENS.surface2,
        border: active
          ? `1px solid ${TOKENS.accent}88`
          : `1px solid ${TOKENS.border}`,
        borderRadius: 7,
        color: active ? TOKENS.text : TOKENS.textDim,
        fontSize: 12,
        fontWeight: 500,
        fontFamily: "inherit",
        cursor: "pointer",
      }}
    >
      {label}
    </button>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      style={{
        padding: "8px 10px",
        borderRadius: 6,
        background: `${TOKENS.error}1A`,
        border: `1px solid ${TOKENS.error}33`,
        color: TOKENS.error,
        fontSize: 11.5,
        lineHeight: 1.4,
      }}
    >
      {message}
    </div>
  );
}

function cancelBtnStyle(submitting: boolean): CSSProperties {
  return {
    height: 30,
    padding: "0 12px",
    background: TOKENS.surface2,
    color: TOKENS.text,
    border: `1px solid ${TOKENS.border}`,
    borderRadius: 7,
    fontSize: 12.5,
    fontWeight: 500,
    fontFamily: "inherit",
    cursor: submitting ? "not-allowed" : "pointer",
    opacity: submitting ? 0.5 : 1,
  };
}

function saveBtnStyle(canSubmit: boolean): CSSProperties {
  return {
    height: 30,
    padding: "0 14px",
    background: TOKENS.accent,
    color: "#fff",
    border: 0,
    borderRadius: 7,
    fontSize: 12.5,
    fontWeight: 600,
    fontFamily: "inherit",
    cursor: canSubmit ? "pointer" : "not-allowed",
    opacity: canSubmit ? 1 : 0.5,
    boxShadow: `0 0 0 1px ${TOKENS.accent}, 0 6px 16px -4px ${TOKENS.accent}88`,
  };
}
