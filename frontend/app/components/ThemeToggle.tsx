"use client";

// Theme switch (Story 10.1, D12). Dark is the default (set before first
// paint by the blocking script in `layout.tsx`, so there is no flash of the
// wrong theme) — this button is the only way to reach light mode, which is
// retained, not removed.
//
// Reads the attribute the blocking script already set rather than deciding
// the initial theme itself, so server and first-client-render markup match
// exactly (`theme` starts null and is filled in one effect after mount) —
// avoiding a hydration warning without needing next-themes as a dependency.

import { useEffect, useState } from "react";
import { MoonIcon, SunIcon } from "./ui/icons";

const STORAGE_KEY = "thesistrace-theme";

export function ThemeToggle() {
  const [theme, setTheme] = useState<"dark" | "light" | null>(null);

  useEffect(() => {
    const current = document.documentElement.getAttribute("data-theme");
    setTheme(current === "light" ? "light" : "dark");
  }, []);

  function toggle() {
    const next = theme === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Private-browsing / storage-blocked: theme still applies for this
      // page view, it just won't persist across visits.
    }
    setTheme(next);
  }

  // Render dark's icon (the default theme) until mounted, matching what the
  // blocking script already painted — avoids a one-frame icon swap on load.
  const showingDark = theme !== "light";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={showingDark ? "Switch to light theme" : "Switch to dark theme"}
      title={showingDark ? "Switch to light theme" : "Switch to dark theme"}
      className="inline-flex h-8 w-8 items-center justify-center rounded-[var(--radius-control)] text-[var(--color-ink-muted)] transition-colors hover:bg-[var(--color-border)]/40 hover:text-[var(--color-ink)]"
    >
      {showingDark ? <SunIcon className="h-4 w-4" /> : <MoonIcon className="h-4 w-4" />}
    </button>
  );
}
