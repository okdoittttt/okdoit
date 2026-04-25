import { useState } from "react";
import { postRun } from "@/lib/api";
import { useSession } from "@/stores/sessionStore";

interface Props {
  /** 입력 가능 여부. status 가 idle/finished/errored/stopped 일 때만 true. */
  enabled: boolean;
  /** controlled value. App 에서 lift up 해 TaskTemplates 와 공유. */
  value: string;
  /** value 변경 콜백. */
  onChange: (next: string) => void;
}

const SUBMIT_HOTKEY_HINT = "⌘ + Enter 로 전송";

/**
 * 작업 입력창 (controlled).
 *
 * Enter 또는 ``⌘+Enter`` 로 전송. 진행 중에는 비활성화된다. 전송 성공하면
 * ``sessionStore.startSession`` 으로 store 에 sessionId/task 를 박는다 — 그 시점에
 * App 의 ``useEventStream(sessionId)`` 가 WS 를 연다.
 */
export function TaskInput({ enabled, value, onChange }: Props) {
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const startSession = useSession((s) => s.startSession);

  const canSubmit = enabled && !submitting && value.trim().length > 0;

  async function submit() {
    if (!canSubmit) return;
    const task = value.trim();
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await postRun({ task, headless: false });
      startSession(res.session_id, task);
      onChange("");
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setSubmitError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-2">
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
            e.preventDefault();
            void submit();
          }
        }}
        rows={3}
        placeholder="예: 내일 서울 날씨 알려줘"
        disabled={!enabled || submitting}
        className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
      />
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-400">{SUBMIT_HOTKEY_HINT}</span>
        <button
          type="button"
          onClick={() => void submit()}
          disabled={!canSubmit}
          className="rounded-md bg-blue-600 px-4 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:bg-gray-300 disabled:text-gray-500"
        >
          {submitting ? "보내는 중…" : "실행"}
        </button>
      </div>
      {submitError && (
        <div className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
          {submitError}
        </div>
      )}
    </div>
  );
}
