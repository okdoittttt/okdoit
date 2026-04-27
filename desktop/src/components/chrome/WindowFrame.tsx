/**
 * macOS 스타일 윈도우 크롬.
 *
 * 36px 타이틀바(드래그 가능) + 트래픽 라이트 + 가운데 타이틀 + 우측 ⚙ 버튼.
 * Body 영역(``children``)은 flex row 로 좌/중/우 패널을 그대로 받는다.
 *
 * Note: ``-webkit-app-region: drag`` 는 Electron 전용. 버튼은 ``no-drag`` 로
 * 풀어줘야 클릭이 먹는다.
 */

import type { CSSProperties, MouseEvent, ReactNode } from "react";
import { TOKENS } from "@/styles/tokens";
import { Icon } from "@/components/common/Icon";

interface Props {
  children: ReactNode;
  onSettingsClick: () => void;
}

const dragStyle: CSSProperties = {
  WebkitAppRegion: "drag",
} as CSSProperties;

const noDragStyle: CSSProperties = {
  WebkitAppRegion: "no-drag",
} as CSSProperties;

/** 우측 ⚙ 버튼과 폭을 맞추는 좌측 spacer (타이틀 정렬용). */
const LEFT_SPACER_PX = 27;

export function WindowFrame({ children, onSettingsClick }: Props) {
  function handleEnter(e: MouseEvent<HTMLButtonElement>): void {
    e.currentTarget.style.background = TOKENS.surface;
  }
  function handleLeave(e: MouseEvent<HTMLButtonElement>): void {
    e.currentTarget.style.background = "transparent";
  }

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        background: TOKENS.bg,
        borderRadius: 12,
        overflow: "hidden",
        border: `1px solid ${TOKENS.border}`,
        boxShadow:
          "0 30px 80px rgba(0,0,0,.5), 0 0 0 1px rgba(255,255,255,.02) inset",
        display: "flex",
        flexDirection: "column",
        position: "relative",
      }}
    >
      <div
        style={{
          ...dragStyle,
          height: 36,
          display: "flex",
          alignItems: "center",
          padding: "0 12px",
          borderBottom: `1px solid ${TOKENS.border}`,
          background: "#0A0A0A",
          flexShrink: 0,
        }}
      >
        <div style={{ width: LEFT_SPACER_PX, flexShrink: 0 }} />
        <div
          style={{
            flex: 1,
            textAlign: "center",
            fontSize: 12,
            fontWeight: 500,
            color: TOKENS.textDim,
            letterSpacing: 0.2,
          }}
        >
          okdoit
          <span
            style={{
              color: TOKENS.textFaint,
              marginLeft: 8,
              fontWeight: 400,
            }}
          >
            · browser agent
          </span>
        </div>
        <button
          type="button"
          onClick={onSettingsClick}
          onMouseEnter={handleEnter}
          onMouseLeave={handleLeave}
          title="Settings"
          style={{
            ...noDragStyle,
            background: "transparent",
            border: 0,
            color: TOKENS.textDim,
            padding: 6,
            borderRadius: 6,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Icon name="gear" size={15} />
        </button>
      </div>
      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>{children}</div>
    </div>
  );
}
