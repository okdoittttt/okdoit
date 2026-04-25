import { useEffect, useState } from "react";
import { PROVIDERS, PROVIDER_ORDER, type LlmProvider } from "@/lib/settings";

interface Props {
  /** 설정이 이미 저장돼 있는 경우(수정 모드)에 호출되는 닫기 콜백. */
  onClose?: () => void;
  /** 헤더 위 안내 메시지. */
  variant: "first-run" | "edit";
}

/**
 * LLM 프로바이더 + API 키 입력 폼.
 *
 * - 첫 실행 시(``first-run``): 닫기 버튼 X. 저장 후 main 이 페이지 reload.
 * - 수정 시(``edit``): 닫기 버튼 노출. 저장만 되고 reload 안 됨(MVP — 변경 적용은
 *   앱 재시작 후).
 */
export function SettingsView({ onClose, variant }: Props) {
  const [provider, setProvider] = useState<LlmProvider>("gemini");
  const [model, setModel] = useState<string>(PROVIDERS["gemini"].defaultModel);
  const [apiKey, setApiKey] = useState<string>("");
  const [ollamaUrl, setOllamaUrl] = useState<string>("http://localhost:11434");
  const [hasKeyAlready, setHasKeyAlready] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 기존 설정이 있으면 폼에 채운다(수정 모드).
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

  // 프로바이더 바꾸면 모델 placeholder 도 갱신.
  function handleProviderChange(next: LlmProvider) {
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

  async function submit() {
    if (!canSubmit) return;
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
        setError(result.error ?? "저장 실패");
        return;
      }
      // restarted=true 면 main 이 곧 reload — UI 는 그대로 두면 페이지가 다시 그려진다.
      // 수정 모드(restarted=false)면 닫기.
      if (!result.restarted && onClose) onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-5 px-6 py-10">
      <header>
        <h1 className="text-xl font-semibold text-gray-900">okdoit 설정</h1>
        <p className="mt-1 text-sm text-gray-600">
          {variant === "first-run"
            ? "처음 실행입니다. LLM 프로바이더와 API 키를 입력하세요. 키는 OS 보안 저장소(Keychain 등)에 저장됩니다."
            : "설정을 변경합니다. 적용은 앱 재시작 후."}
        </p>
      </header>

      {/* 프로바이더 */}
      <section className="space-y-2">
        <label className="block text-xs font-semibold uppercase tracking-wide text-gray-500">
          LLM 프로바이더
        </label>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {PROVIDER_ORDER.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => handleProviderChange(p)}
              className={`rounded-md border px-3 py-2 text-sm transition ${
                provider === p
                  ? "border-blue-500 bg-blue-50 text-blue-900"
                  : "border-gray-200 bg-white text-gray-700 hover:border-blue-300"
              }`}
            >
              {PROVIDERS[p].label}
            </button>
          ))}
        </div>
      </section>

      {/* 모델 */}
      <section className="space-y-2">
        <label className="block text-xs font-semibold uppercase tracking-wide text-gray-500">
          모델
        </label>
        <input
          type="text"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          placeholder={meta.defaultModel}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </section>

      {/* API 키 (ollama 가 아닐 때만) */}
      {needsApiKey && (
        <section className="space-y-2">
          <label className="block text-xs font-semibold uppercase tracking-wide text-gray-500">
            API 키 ({meta.apiKeyEnv})
          </label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={
              hasKeyAlready
                ? "이미 저장됨 (변경하려면 새 키 입력)"
                : "키를 붙여넣으세요"
            }
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          {meta.apiKeyHelpUrl && (
            <p className="text-xs text-gray-500">
              키 발급:{" "}
              <a
                href={meta.apiKeyHelpUrl}
                target="_blank"
                rel="noreferrer"
                className="text-blue-600 hover:underline"
              >
                {meta.apiKeyHelpUrl}
              </a>
            </p>
          )}
        </section>
      )}

      {/* Ollama 전용 — base URL */}
      {provider === "ollama" && (
        <section className="space-y-2">
          <label className="block text-xs font-semibold uppercase tracking-wide text-gray-500">
            Ollama Base URL
          </label>
          <input
            type="text"
            value={ollamaUrl}
            onChange={(e) => setOllamaUrl(e.target.value)}
            placeholder="http://localhost:11434"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </section>
      )}

      {error && (
        <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="flex items-center justify-end gap-2">
        {onClose && variant === "edit" && (
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="rounded-md bg-white px-4 py-1.5 text-sm font-medium text-gray-700 ring-1 ring-gray-300 hover:bg-gray-50"
          >
            취소
          </button>
        )}
        <button
          type="button"
          onClick={() => void submit()}
          disabled={!canSubmit}
          className="rounded-md bg-blue-600 px-4 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:bg-gray-300 disabled:text-gray-500"
        >
          {submitting ? "저장 중…" : variant === "first-run" ? "저장하고 시작" : "저장"}
        </button>
      </div>
    </div>
  );
}
