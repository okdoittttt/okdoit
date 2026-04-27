/**
 * artifact 를 JSON 으로 그리는 뷰.
 *
 * design/app.jsx 의 ``JsonRender`` 동일한 정규식 기반 syntax highlighter 를
 * 사용한다(키: cyan, 문자열: amber, 불리언/null: purple, 숫자: green).
 */

import { useMemo } from "react";
import { FONT_MONO, TOKENS } from "@/styles/tokens";
import type { SessionArtifact } from "@/types/artifact";

interface Props {
  artifact: SessionArtifact | null;
  fallback: { task: string; result: string | null; error: string | null; iterations: number };
}

const ESCAPE: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;" };

function highlight(json: string): string {
  return json
    .replace(/[&<>]/g, (c) => ESCAPE[c] ?? c)
    .replace(
      /("(?:\\.|[^"\\])*")(\s*:)/g,
      `<span style="color:${TOKENS.cyan}">$1</span>$2`,
    )
    .replace(
      /: ("(?:\\.|[^"\\])*")/g,
      `: <span style="color:#FBBF24">$1</span>`,
    )
    .replace(
      /\b(true|false|null)\b/g,
      `<span style="color:${TOKENS.purple}">$1</span>`,
    )
    .replace(
      /(?<=:\s)(-?\d+\.?\d*)/g,
      `<span style="color:${TOKENS.success}">$1</span>`,
    );
}

export function JsonView({ artifact, fallback }: Props) {
  const html = useMemo(() => {
    const data = artifact ?? fallback;
    return highlight(JSON.stringify(data, null, 2));
  }, [artifact, fallback]);

  return (
    <pre
      style={{
        margin: 0,
        fontSize: 11.5,
        lineHeight: 1.55,
        fontFamily: FONT_MONO,
        color: TOKENS.text,
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
      }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
