/**
 * 디자인 시안의 라인-아트 SVG 아이콘 모음.
 *
 * 각 아이콘은 16×16 viewBox 에 stroke 1.4 로 통일. ``play`` / ``pause`` /
 * ``stop`` 만 fill 도 사용한다. 아이콘 이름이 없으면 ``null`` 을 돌려준다.
 */

export type IconName =
  | "plus"
  | "gear"
  | "play"
  | "pause"
  | "stop"
  | "copy"
  | "chev"
  | "corner"
  | "globe"
  | "arrow"
  | "spark"
  | "check"
  | "x"
  | "cmd"
  | "reload"
  | "trash";

interface Props {
  name: IconName;
  size?: number;
  color?: string;
}

export function Icon({ name, size = 14, color = "currentColor" }: Props) {
  const props = {
    width: size,
    height: size,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: color,
    strokeWidth: 1.4,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  switch (name) {
    case "plus":
      return (
        <svg {...props}>
          <path d="M8 3v10M3 8h10" />
        </svg>
      );
    case "gear":
      return (
        <svg {...props}>
          <circle cx="8" cy="8" r="2" />
          <path d="M8 1.5v1.8M8 12.7v1.8M3.4 3.4l1.3 1.3M11.3 11.3l1.3 1.3M1.5 8h1.8M12.7 8h1.8M3.4 12.6l1.3-1.3M11.3 4.7l1.3-1.3" />
        </svg>
      );
    case "play":
      return (
        <svg {...props}>
          <path d="M5 3l8 5-8 5z" fill={color} />
        </svg>
      );
    case "pause":
      return (
        <svg {...props}>
          <rect x="4" y="3" width="3" height="10" fill={color} />
          <rect x="9" y="3" width="3" height="10" fill={color} />
        </svg>
      );
    case "stop":
      return (
        <svg {...props}>
          <rect x="4" y="4" width="8" height="8" fill={color} />
        </svg>
      );
    case "copy":
      return (
        <svg {...props}>
          <rect x="3" y="3" width="8" height="8" rx="1.2" />
          <path d="M5.5 13h7a1 1 0 0 0 1-1V6" />
        </svg>
      );
    case "chev":
      return (
        <svg {...props}>
          <path d="M5 6l3 3 3-3" />
        </svg>
      );
    case "corner":
      return (
        <svg {...props}>
          <path d="M3 3h10v10H3z" />
          <path d="M6 6l4 4M10 6l-4 4" />
        </svg>
      );
    case "globe":
      return (
        <svg {...props}>
          <circle cx="8" cy="8" r="5.5" />
          <path d="M2.5 8h11M8 2.5c1.6 1.6 2.5 3.4 2.5 5.5S9.6 12.4 8 14c-1.6-1.6-2.5-3.4-2.5-5.5S6.4 4.1 8 2.5z" />
        </svg>
      );
    case "arrow":
      return (
        <svg {...props}>
          <path d="M3 8h10M9 4l4 4-4 4" />
        </svg>
      );
    case "spark":
      return (
        <svg {...props}>
          <path d="M8 2v4M8 10v4M2 8h4M10 8h4" stroke={color} />
        </svg>
      );
    case "check":
      return (
        <svg {...props}>
          <path d="M3 8.5l3 3 7-7" />
        </svg>
      );
    case "x":
      return (
        <svg {...props}>
          <path d="M4 4l8 8M12 4l-8 8" />
        </svg>
      );
    case "cmd":
      return (
        <svg {...props}>
          <path d="M5 3a2 2 0 0 0 0 4h6a2 2 0 0 0 0-4 2 2 0 0 0-2 2v6a2 2 0 0 0 2 2 2 2 0 0 0 0-4H5a2 2 0 0 0 0 4 2 2 0 0 0 2-2V5a2 2 0 0 0-2-2z" />
        </svg>
      );
    case "reload":
      return (
        <svg {...props}>
          <path d="M3 8a5 5 0 0 1 8.5-3.5L13 6" />
          <path d="M13 3v3h-3" />
          <path d="M13 8a5 5 0 0 1-8.5 3.5L3 10" />
          <path d="M3 13v-3h3" />
        </svg>
      );
    case "trash":
      return (
        <svg {...props}>
          <path d="M3 4.5h10" />
          <path d="M6 4.5V3a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v1.5" />
          <path d="M4.5 4.5l.6 8.2a1 1 0 0 0 1 .8h3.8a1 1 0 0 0 1-.8l.6-8.2" />
          <path d="M7 7v4M9 7v4" />
        </svg>
      );
    default:
      return null;
  }
}
