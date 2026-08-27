"use client";

// Theme switch (Story 10.1/10.2, D12). Dark is the default; this button is
// the only way to reach light mode, which is retained, not removed.
//
// `initialTheme` comes from the server (RootLayout reads the cookie and
// renders `data-theme` directly on <html> — see layout.tsx's comment for why
// a pre-hydration script mutating the DOM does NOT work in this stack).
// Because the server already knows the real theme, this component's first
// render can just use it — no mount-guard/placeholder dance needed to dodge
// a hydration mismatch, because there isn't one: server and client agree
// from the first frame.

import { useState } from "react";
import { MoonIcon, SunIcon } from "./ui/icons";

const THEME_COOKIE = "thesistrace-theme";

export function ThemeToggle({ initialTheme }: { initialTheme: "dark" | "light" }) {
  const [theme, setTheme] = useState(initialTheme);

  function toggle() {
    const next = theme === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    // A cookie, not localStorage: the SERVER reads this on the next request
    // to render the correct `data-theme` directly, which is what makes the
    // choice stick without a client-only script racing hydration.
    document.cookie = `${THEME_COOKIE}=${next}; path=/; max-age=31536000; SameSite=Lax`;
    setTheme(next);
  }

  const showingDark = theme === "dark";

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
