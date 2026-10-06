"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  isThemePreference,
  THEME_MEDIA_QUERY,
  THEME_STORAGE_KEY,
  type ThemePreference,
} from "@/lib/theme";

const ThemeContext = createContext<{
  preference: ThemePreference;
  ready: boolean;
  setPreference: (preference: ThemePreference) => void;
} | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Stable server/client first render; bootstrap has already resolved the palette.
  const [preference, setPreferenceState] = useState<ThemePreference>("system");
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const media = window.matchMedia(THEME_MEDIA_QUERY);
    let current: ThemePreference = "system";
    try {
      const saved = localStorage.getItem(THEME_STORAGE_KEY);
      if (isThemePreference(saved)) current = saved;
    } catch {
      /* Theme remains available when storage is blocked. */
    }
    const apply = () => {
      document.documentElement.dataset.theme =
        current === "system" ? (media.matches ? "dark" : "light") : current;
    };
    const changed = (event: StorageEvent) => {
      if (event.key !== THEME_STORAGE_KEY && event.key !== null) return;
      current = isThemePreference(event.newValue) ? event.newValue : "system";
      setPreferenceState(current);
      apply();
    };
    const selected = (event: Event) => {
      const value: unknown = (event as CustomEvent<unknown>).detail;
      if (!isThemePreference(value)) return;
      current = value;
      setPreferenceState(current);
      apply();
    };
    setPreferenceState(current);
    apply();
    setReady(true);
    media.addEventListener("change", apply);
    window.addEventListener("storage", changed);
    window.addEventListener("academic-theme-change", selected);
    return () => {
      media.removeEventListener("change", apply);
      window.removeEventListener("storage", changed);
      window.removeEventListener("academic-theme-change", selected);
    };
  }, []);
  function setPreference(value: ThemePreference) {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, value);
    } catch {
      /* Session-only fallback. */
    }
    window.dispatchEvent(
      new CustomEvent("academic-theme-change", { detail: value }),
    );
  }
  return (
    <ThemeContext.Provider value={{ preference, ready, setPreference }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("Theme controls require ThemeProvider.");
  return context;
}
