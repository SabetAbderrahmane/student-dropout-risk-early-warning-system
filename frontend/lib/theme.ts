export type ThemePreference = "light" | "dark" | "system";
export const THEME_STORAGE_KEY = "academic-early-warning-theme";
export const THEME_MEDIA_QUERY = "(prefers-color-scheme: dark)";
export function isThemePreference(value: unknown): value is ThemePreference {
  return value === "light" || value === "dark" || value === "system";
}

// Parser-blocking inline bootstrap in <head>: runs before the body can paint.
// Keep this independent of React and tolerate blocked/unavailable browser storage.
export const THEME_INITIALIZATION = `(() => {
  let preference = "system";
  try {
    const saved = localStorage.getItem("${THEME_STORAGE_KEY}");
    if (saved === "light" || saved === "dark" || saved === "system") preference = saved;
  } catch {}
  document.documentElement.dataset.theme = preference === "system"
    ? (matchMedia("${THEME_MEDIA_QUERY}").matches ? "dark" : "light")
    : preference;
})();`;
