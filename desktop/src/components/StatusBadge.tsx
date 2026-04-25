import type { SessionStatus } from "@/stores/sessionStore";

const LABELS: Record<SessionStatus, string> = {
  idle: "대기",
  running: "실행 중",
  paused: "일시정지",
  finished: "완료",
  errored: "오류",
  stopped: "중단됨",
};

const CLASSES: Record<SessionStatus, string> = {
  idle: "bg-gray-100 text-gray-600",
  running: "bg-blue-100 text-blue-700",
  paused: "bg-yellow-100 text-yellow-800",
  finished: "bg-green-100 text-green-700",
  errored: "bg-red-100 text-red-700",
  stopped: "bg-gray-200 text-gray-700",
};

interface Props {
  status: SessionStatus;
}

/**
 * 세션 상태를 색상 배지로 표시한다.
 *
 * 상태 종류는 ``SessionStatus`` 와 정확히 일치 — 새 상태가 추가되면 여기에 매핑을
 * 추가해야 TypeScript 가 알려준다(Record 타입의 strict 키 검사).
 */
export function StatusBadge({ status }: Props) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${CLASSES[status]}`}
    >
      {LABELS[status]}
    </span>
  );
}
