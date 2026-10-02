export type IconName =
  | "shield"
  | "grid"
  | "students"
  | "import"
  | "warning"
  | "activity"
  | "settings"
  | "logout"
  | "menu"
  | "close"
  | "arrow"
  | "play"
  | "refresh"
  | "check";
const paths: Record<IconName, string> = {
  shield: "M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Z M8 12l3 3 5-6",
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  students: "m2 8 10-5 10 5-10 5-10-5Z M6 10v7c4 3 8 3 12 0v-7 M22 8v8",
  import: "M14 2H5v20h14V7l-5-5Z M14 2v5h5 M12 18V10 M9 13l3-3 3 3",
  warning: "m12 3 10 18H2L12 3Z M12 9v5 M12 17v1",
  activity: "M3 19V5 M3 19h18 M6 14l4-5 4 3 6-8",
  settings:
    "M12 3v3 M12 18v3 M3 12h3 M18 12h3 M5 5l3 3 M16 16l3 3 M5 19l3-3 M16 8l3-3 M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
  logout: "M9 3H4v18h5 M9 12h12 M17 8l4 4-4 4",
  menu: "M3 6h18 M3 12h18 M3 18h18",
  close: "m6 6 12 12 M6 18 18 6",
  arrow: "M4 12h16 M14 6l6 6-6 6",
  play: "m9 7 8 5-8 5V7Z M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  refresh: "M20 7a9 9 0 1 0 1 8 M20 2v5h-5",
  check: "m5 12 4 4 10-10",
};
export function Icon({ name }: { name: IconName }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name]} />
    </svg>
  );
}
