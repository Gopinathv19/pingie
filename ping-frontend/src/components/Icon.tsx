// Square-cap stroke icons from the design reference.
const paths = {
  overview: "M3 3h8v8H3zM13 3h8v5h-8zM13 10h8v11h-8zM3 13h8v8H3z",
  conversations: "M4 4h16v12H9l-5 4z",
  knowledge: "M6 3h9l4 4v14H6zM14 3v5h5M9 13h7M9 17h7",
  test: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-3.5-3.5",
  appearance: "M4 20l4-1L19 8l-3-3L5 16zM14 7l3 3",
  install: "M8 8l-4 4 4 4M16 8l4 4-4 4M13.5 5l-3 14",
  domains:
    "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c2.5 2.5 3.8 5.5 3.8 9s-1.3 6.5-3.8 9c-2.5-2.5-3.8-5.5-3.8-9S9.5 5.5 12 3z",
  settings: "M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1M15 4v4M9 10v4M17 16v4",
  back: "M15 6l-6 6 6 6",
  chevrons: "M8 9l4-4 4 4M8 15l4 4 4-4",
  plus: "M12 5v14M5 12h14",
  close: "M6 6l12 12M18 6L6 18",
  edit: "M4 20h4L19 9l-4-4L4 16v4zM14 6l4 4",
  copy: "M8 8h12v12H8zM4 16V4h12",
  check: "M5 12l5 5 9-10",
  upload: "M12 16V4M7 9l5-5 5 5M4 20h16",
  link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  refresh: "M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7",
  trash: "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3",
  file: "M6 3h9l4 4v14H6zM14 3v5h5",
  globe:
    "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c2.5 2.5 3.8 5.5 3.8 9s-1.3 6.5-3.8 9c-2.5-2.5-3.8-5.5-3.8-9S9.5 5.5 12 3z",
  send: "M4 12l16-8-6 16-3-7z",
  thumbUp: "M7 11v9H4v-9zM7 11l4-8c1.5 0 2.5 1 2.5 2.5V9h5.5l-2 11H7",
  thumbDown: "M7 13V4H4v9zM7 13l4 8c1.5 0 2.5-1 2.5-2.5V15h5.5l-2-11H7",
  mail: "M3 5h18v14H3zM3 5l9 8 9-8",
  spark: "M12 3v6M12 15v6M3 12h6M15 12h6M6 6l3 3M15 15l3 3M18 6l-3 3M9 15l-3 3",
  help: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.7v.5M12 17v.5",
  more: "M5 12h.01M12 12h.01M19 12h.01",
  external: "M14 4h6v6M20 4l-9 9M18 14v6H4V6h6",
  pause: "M8 5v14M16 5v14",
  play: "M7 4l13 8-13 8z",
  filter: "M4 5h16l-6 8v6l-4-2v-4z",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
  moon: "M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z",
} as const;

export type IconName = keyof typeof paths;

interface IconProps {
  name: IconName;
  size?: number;
  strokeWidth?: number;
  className?: string;
  style?: React.CSSProperties;
}

export function Icon({ name, size = 16, strokeWidth = 1.9, className, style }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="square"
      strokeLinejoin="miter"
      className={className}
      style={style}
    >
      <path d={paths[name]} />
    </svg>
  );
}
