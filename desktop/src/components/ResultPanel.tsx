interface Props {
  result: string | null;
  error: string | null;
  iterations: number;
}

/**
 * 세션 종료 후 결과 또는 에러를 표시한다.
 *
 * 둘 다 ``null`` 이면 컴포넌트 자체를 렌더하지 않는다(상위에서 분기).
 */
export function ResultPanel({ result, error, iterations }: Props) {
  if (error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-red-700">
          오류
        </div>
        <div className="mt-1 whitespace-pre-wrap break-words text-sm text-red-900">
          {error}
        </div>
        <div className="mt-2 text-xs text-red-500">반복 {iterations}회 후 종료</div>
      </div>
    );
  }

  if (result) {
    return (
      <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
          결과
        </div>
        <div className="mt-1 whitespace-pre-wrap break-words text-sm text-gray-900">
          {result}
        </div>
        <div className="mt-2 text-xs text-emerald-600">반복 {iterations}회</div>
      </div>
    );
  }

  return null;
}
