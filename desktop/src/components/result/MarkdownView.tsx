/**
 * artifact.result 의 마크다운 텍스트 뷰.
 *
 * 외부 라이브러리 없이 ``<pre>`` 로 그대로 표시한다. 결과가 ``null`` 이면
 * "(empty)" placeholder.
 */

import { TOKENS } from "@/styles/tokens";

interface Props {
  result: string | null;
  error: string | null;
}

export function MarkdownView({ result, error }: Props) {
  if (error) {
    return (
      <div
        style={{
          fontSize: 12.5,
          color: TOKENS.error,
          lineHeight: 1.55,
          whiteSpace: "pre-wrap",
          fontFamily: "inherit",
        }}
      >
        {error}
      </div>
    );
  }
  if (!result) {
    return (
      <div
        style={{
          fontSize: 12,
          color: TOKENS.textFaint,
          fontStyle: "italic",
          padding: "8px 0",
        }}
      >
        (no result text)
      </div>
    );
  }
  return (
    <pre
      style={{
        margin: 0,
        fontSize: 12.5,
        color: TOKENS.text,
        lineHeight: 1.6,
        fontFamily: "inherit",
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
      }}
    >
      {result}
    </pre>
  );
}
