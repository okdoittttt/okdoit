interface Template {
  title: string;
  task: string;
}

const TEMPLATES: ReadonlyArray<Template> = [
  {
    title: "오늘 / 내일 날씨",
    task: "내일 서울 날씨 알려줘",
  },
  {
    title: "GitHub 트렌딩",
    task: "오늘 GitHub trending 의 Python 저장소 5개 이름과 한 줄 설명을 알려줘",
  },
  {
    title: "환율 조회",
    task: "오늘 미국 달러 환율 알려줘",
  },
  {
    title: "유튜브 검색",
    task: "유튜브에서 '리액트 18 새로운 기능' 검색해서 상위 3개 영상 제목 알려줘",
  },
];

interface Props {
  /** 카드 클릭 시 입력창에 채워 넣을 콜백. */
  onSelect: (task: string) => void;
}

/**
 * idle 상태에서 입력창 빈 화면을 채우는 추천 작업 카드.
 *
 * 카드 클릭 시 ``onSelect`` 로 입력창에 텍스트를 주입한다 — 실행은 사용자가 직접
 * 한 번 더 확인하고 누르도록 의도적으로 분리.
 */
export function TaskTemplates({ onSelect }: Props) {
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {TEMPLATES.map((t) => (
        <button
          key={t.title}
          type="button"
          onClick={() => onSelect(t.task)}
          className="rounded-md border border-gray-200 bg-white px-3 py-2 text-left transition hover:border-blue-300 hover:bg-blue-50"
        >
          <div className="text-sm font-semibold text-gray-800">{t.title}</div>
          <div className="mt-0.5 text-xs text-gray-500">{t.task}</div>
        </button>
      ))}
    </div>
  );
}
