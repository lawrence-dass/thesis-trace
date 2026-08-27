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
    // Read the attribute as the source of truth so even an unusually early
    // click cannot invert the still-null React state incorrectly.
    const current = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
    const next = current === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Private-browsing / storage-blocked: theme still applies for this
      // page view, it just won't persist across visits.
    }
    setTheme(next);
  }

  // Keep a stable, non-theme-dependent placeholder until the effect has read
  // the script-selected attribute. An assumed icon/label can be wrong for a
  // returning light-mode visitor during that first client render.
  const mounted = theme !== null;
  const showingDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={!mounted}
      aria-label={mounted ? (showingDark ? "Switch to light theme" : "Switch to dark theme") : "Theme"}
      title={mounted ? (showingDark ? "Switch to light theme" : "Switch to dark theme") : "Theme"}
      className="inline-flex h-8 w-8 items-center justify-center rounded-[var(--radius-control)] text-[var(--color-ink-muted)] transition-colors hover:bg-[var(--color-border)]/40 hover:text-[var(--color-ink)]"
    >
      {mounted ? (
        showingDark ? <SunIcon className="h-4 w-4" /> : <MoonIcon className="h-4 w-4" />
      ) : (
        <span className="h-4 w-4" aria-hidden="true" />
      )}
    </button>
  );
}
