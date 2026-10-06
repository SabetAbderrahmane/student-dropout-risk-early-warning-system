import type { ReactNode } from "react";

// One optical grid and stroke weight; each workspace has its own pictogram.
const artwork = {
  shield: (
    <>
      <path d="M12 3 4.5 6v5.8c0 4.3 3 7.1 7.5 9.2 4.5-2.1 7.5-4.9 7.5-9.2V6L12 3Z" />
      <path d="m8.5 12 2.3 2.3 4.7-4.6" />
    </>
  ),
  grid: (
    <>
      <rect x="3.5" y="3.5" width="7" height="7" rx="1.7" />
      <rect x="13.5" y="3.5" width="7" height="11" rx="1.7" />
      <rect x="3.5" y="13.5" width="7" height="7" rx="1.7" />
      <path d="M14 19.5h6" />
    </>
  ),
  students: (
    <>
      <circle cx="9" cy="8" r="3" />
      <path d="M3.5 20v-2a5.5 5.5 0 0 1 11 0v2M16 5.2a3 3 0 0 1 0 5.6M17.5 14a5 5 0 0 1 3 4.6V20" />
    </>
  ),
  import: (
    <>
      <path d="M12 3v11m-4-4 4 4 4-4M4 14v5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5" />
      <path d="M4 15h3l2 3h6l2-3h3" />
    </>
  ),
  warning: (
    <>
      <path d="M5 13V9a7 7 0 0 1 14 0v4l2 4H3l2-4ZM9 20h6" />
      <path d="M12 6.5v4m0 2v.2" />
    </>
  ),
  activity: (
    <>
      <path d="M4 3.5v17h17M8 16v-4M13 16V8M18 16V5" />
    </>
  ),
  casework: (
    <>
      <path d="M3.5 8.5V6a2 2 0 0 1 2-2H10l2.5 3H19a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5.5a2 2 0 0 1-2-2v-9Z" />
      <path d="M8 12h8m-8 4h5" />
    </>
  ),
  calendar: (
    <>
      <rect x="3.5" y="5" width="17" height="16" rx="2.5" />
      <path d="M7.5 3v4m9-4v4M3.5 10h17m-13 5 2.5 2.5 4.5-4.5" />
    </>
  ),
  settings: (
    <>
      <path d="M4 7h16M4 17h16" />
      <rect x="7" y="4" width="4" height="6" rx="1" />
      <rect x="14" y="14" width="4" height="6" rx="1" />
    </>
  ),
  logout: (
    <>
      <path d="M9 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4M9 12h12m-4-4 4 4-4 4" />
    </>
  ),
  menu: <path d="M4 6h16M4 12h12M4 18h16" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
  play: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m10 8 6 4-6 4V8Z" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 5v5h-5M4 19v-5h5" />
      <path d="M5.2 7a8 8 0 0 1 13.2-1L20 10M4 14l1.6 4A8 8 0 0 0 18.8 17" />
    </>
  ),
  check: <path d="m5 12 4 4L19 6" />,
  help: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.5 9a2.5 2.5 0 1 1 4 2c-1 .7-1.5 1.2-1.5 2.5M12 16.5v.2" />
    </>
  ),
  book: (
    <>
      <path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1Zm0 0v15" />
      <path d="M6 8h3m-3 4h3m6-4h3m-3 4h3" />
    </>
  ),
  chevron: <path d="m9 5 7 7-7 7" />,
  back: <path d="m14 5-7 7 7 7" />,
} satisfies Record<string, ReactNode>;
export type IconName = keyof typeof artwork;
export function Icon({ name }: { name: IconName }) {
  return (
    <svg
      className="app-icon"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {artwork[name]}
    </svg>
  );
}
