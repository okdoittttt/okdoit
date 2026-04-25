import { useState } from "react";
import { postPause, postResume, postStop } from "@/lib/api";
import type { SessionStatus } from "@/stores/sessionStore";

type Action = "pause" | "resume" | "stop";

interface Props {
  sessionId: string;
  status: SessionStatus;
}

const ACTION_HANDLERS: Record<Action, (sid: string) => Promise<void>> = {
  pause: postPause,
  resume: postResume,
  stop: postStop,
};

const ACTION_LABEL: Record<Action, string> = {
  pause: "일시정지",
  resume: "재개",
  stop: "중단",
};

const PRIMARY_BTN =
  "rounded-md bg-white border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed";

const DANGER_BTN =
  "rounded-md bg-white border border-red-300 px-3 py-1.5 text-xs font-medium text-red-700 shadow-sm transition hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed";

/**
 * 실행 제어 버튼 그룹.
 *
 * 노출 정책:
 *   - running  → [일시정지] [중단]
 *   - paused   → [재개]    [중단]
 *   - 그 외     → 렌더하지 않음
 *
 * 호출 중인 액션은 disabled 로 잠근다(중복 클릭 방지).
 */
export function ControlButtons({ sessionId, status }: Props) {
  const [pending, setPending] = useState<Action | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handle(action: Action) {
    setPending(action);
    setError(null);
    try {
      await ACTION_HANDLERS[action](sessionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPending(null);
    }
  }

  function renderButton(action: Action, danger = false) {
    return (
      <button
        type="button"
        onClick={() => void handle(action)}
        disabled={pending !== null}
        className={danger ? DANGER_BTN : PRIMARY_BTN}
      >
        {pending === action ? "…" : ACTION_LABEL[action]}
      </button>
    );
  }

  if (status !== "running" && status !== "paused") return null;

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex gap-2">
        {status === "running" && renderButton("pause")}
        {status === "paused" && renderButton("resume")}
        {renderButton("stop", true)}
      </div>
      {error && <span className="text-[10px] text-red-600">{error}</span>}
    </div>
  );
}
