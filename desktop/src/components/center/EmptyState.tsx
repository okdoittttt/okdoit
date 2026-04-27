/** 활동 로그가 비었을 때 표시하는 placeholder. */

import { TOKENS } from "@/styles/tokens";
import { Icon } from "@/components/common/Icon";

interface Props {
  accent: string;
}

export function EmptyState({ accent }: Props) {
  return (
    <div
      style={{
        padding: "60px 0",
        textAlign: "center",
        color: TOKENS.textFaint,
        fontSize: 13,
      }}
    >
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: 10,
          margin: "0 auto 14px",
          background: `${accent}14`,
          border: `1px solid ${accent}33`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Icon name="spark" size={20} color={accent} />
      </div>
      <div
        style={{
          color: TOKENS.textDim,
          fontWeight: 500,
          marginBottom: 4,
          fontSize: 13,
        }}
      >
        Ready when you are
      </div>
      <div style={{ fontSize: 12 }}>
        Type a task above or pick from the sidebar.
      </div>
    </div>
  );
}
