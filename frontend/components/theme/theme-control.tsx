"use client";

import { useId } from "react";
import { isThemePreference } from "@/lib/theme";
import { useTheme } from "./theme-provider";

export function ThemeControl() {
  const id = useId();
  const { preference, ready, setPreference } = useTheme();
  return (
    <label className="theme-control" htmlFor={id}>
      <span>Theme</span>
      <select
        id={id}
        value={preference}
        disabled={!ready}
        onChange={(event) => {
          if (isThemePreference(event.target.value))
            setPreference(event.target.value);
        }}
      >
        <option value="light">Light</option>
        <option value="dark">Dark</option>
        <option value="system">System</option>
      </select>
    </label>
  );
}
