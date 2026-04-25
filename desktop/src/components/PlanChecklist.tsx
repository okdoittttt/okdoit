import { useEffect } from "react";
import type { Subtask } from "@/types/events";
import { useSessions } from "@/stores/sessionStore";

const REPLAN_FLASH_DURATION_MS = 1500;

interface Props {
  subtasks: Subtask[];
  activeIndex: number;
  /** plan.replanned 직후 강조 플래시 여부. */
  replanFlash: boolean;
  /** 플래시 끄기 액션을 store 에 디스패치하기 위한 sid. */
  sessionId: string;
}

/**
 * plan / replan 결과를 체크리스트 UI 로 보여준다.
 *
 * - 완료된 항목: 초록 ✓
 * - active 항목: 진한 파란색 + ▶ 표시
 * - 그 외: 회색
 *
 * ``replanFlash`` 가 켜지면 잠깐 노란 바를 띄워 사용자에게 계획 변경을 알린다.
 */
export function PlanChecklist({ subtasks, activeIndex, replanFlash, sessionId }: Props) {
  const clearReplanFlash = useSessions((s) => s.clearReplanFlash);

  useEffect(() => {
    if (!replanFlash) return;
    const timer = window.setTimeout(
      () => clearReplanFlash(sessionId),
      REPLAN_FLASH_DURATION_MS,
    );
    return () => window.clearTimeout(timer);
  }, [replanFlash, sessionId, clearReplanFlash]);

  if (subtasks.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-gray-300 px-3 py-6 text-center text-xs text-gray-400">
        계획 대기 중…
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {replanFlash && (
        <div className="rounded-md bg-yellow-50 px-3 py-2 text-xs text-yellow-800">
          계획이 변경되었습니다.
        </div>
      )}
      <ol className="space-y-1">
        {subtasks.map((s) => {
          const isActive = s.index === activeIndex && !s.done;
          return (
            <li
              key={s.index}
              className={`flex items-start gap-2 rounded-md px-2 py-1.5 text-sm ${
                isActive ? "bg-blue-50 text-blue-900" : "text-gray-700"
              }`}
            >
              <span className="w-5 shrink-0 select-none text-center">
                {s.done ? "✓" : isActive ? "▶" : "·"}
              </span>
              <span className={s.done ? "text-gray-400 line-through" : ""}>
                {s.description}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
