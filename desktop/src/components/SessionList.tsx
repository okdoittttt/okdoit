import type { SessionData } from "@/stores/sessionStore";
import { StatusBadge } from "@/components/StatusBadge";

interface Props {
  sessions: SessionData[];
  activeId: string | null;
  /** ``null`` 이면 "새 세션 시작" 화면으로 전환. */
  onSelect: (sessionId: string | null) => void;
}

/**
 * 좌측 세션 리스트 패널.
 *
 * 상단 "+ 새 세션" 버튼은 ``onSelect(null)`` 을 호출해 idle 화면으로 보낸다.
 * 세션 카드 클릭 시 해당 세션을 active 로 만든다(이전 세션 유지).
 */
export function SessionList({ sessions, activeId, onSelect }: Props) {
  return (
    <div className="flex h-full flex-col bg-gray-50">
      <div className="border-b border-gray-200 p-3">
        <button
          type="button"
          onClick={() => onSelect(null)}
          className="w-full rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white shadow-sm transition hover:bg-blue-700"
        >
          + 새 세션
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-2">
        {sessions.length === 0 ? (
          <div className="px-2 py-4 text-center text-xs text-gray-400">
            아직 세션이 없습니다.
          </div>
        ) : (
          <ul className="space-y-1">
            {sessions.map((s) => {
              const isActive = activeId === s.id;
              return (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(s.id)}
                    className={`block w-full rounded-md px-2.5 py-2 text-left transition ${
                      isActive
                        ? "bg-white shadow-sm ring-1 ring-blue-200"
                        : "hover:bg-white"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <StatusBadge status={s.status} />
                      <span className="text-[10px] text-gray-400">
                        {formatTime(s.startedAt)}
                      </span>
                    </div>
                    <div
                      className="mt-1 break-words text-xs text-gray-700"
                      style={{
                        display: "-webkit-box",
                        WebkitBoxOrient: "vertical",
                        WebkitLineClamp: 2,
                        overflow: "hidden",
                      }}
                    >
                      {s.task}
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

function formatTime(ts: number): string {
  const d = new Date(ts);
  const hh = d.getHours().toString().padStart(2, "0");
  const mm = d.getMinutes().toString().padStart(2, "0");
  return `${hh}:${mm}`;
}
