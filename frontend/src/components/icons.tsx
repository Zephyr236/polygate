/**
 * Small inline icon set. No emoji, no icon-font dependency.
 */

export type IconName =
  | "dashboard"
  | "server"
  | "route"
  | "play"
  | "logout"
  | "plus"
  | "save"
  | "search"
  | "refresh"
  | "alert"
  | "check"
  | "pulse"
  | "key"
  | "chevron";

const PATHS: Record<IconName, string> = {
  dashboard: "M4 4h6v7H4zM14 4h6v4h-6zM14 12h6v8h-6zM4 15h6v5H4z",
  server: "M4 5h16v5H4zM4 14h16v5H4zM7 7.5h.01M7 16.5h.01",
  route: "M4 6h6a4 4 0 0 1 0 8H8a4 4 0 0 0 0 8h12M17 4l3 3-3 3M17 18l3 3-3 3",
  play: "M8 5l11 7-11 7z",
  logout: "M10 5H5v14h5M14 8l4 4-4 4M9 12h9",
  plus: "M12 5v14M5 12h14",
  save: "M5 4h11l3 3v13H5zM8 4v6h7V4M8 20v-6h8v6",
  search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM16.5 16.5L21 21",
  refresh: "M20 11a8 8 0 0 0-14-4L4 9M4 5v4h4M4 13a8 8 0 0 0 14 4l2-2M20 19v-4h-4",
  alert: "M12 4l9 16H3zM12 9v5M12 17h.01",
  check: "M5 12l4 4L19 6",
  pulse: "M3 12h4l2-7 4 14 2-7h6",
  key: "M15 7a4 4 0 1 1-3.5 5.9L4 20.5V17h3v-3h3l1.5-1.1A4 4 0 0 1 15 7z",
  chevron: "M8 10l4 4 4-4",
};

/** Render one inline icon. */
export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
