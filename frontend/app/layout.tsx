import type { Metadata } from "next";
import type { ReactNode } from "react";
import { cookies } from "next/headers";
import { JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import { ThemeToggle } from "./components/ThemeToggle";
import "./globals.css";

// Theme comes from a COOKIE, read server-side, and rendered directly as the
// `data-theme` attribute — not a pre-hydration script mutating the DOM.
//
// That was the first design and it does not work in this stack: a script
// setting `data-theme` before hydration creates a genuine server/client
// attribute mismatch on <html>, and React's hydration reconciliation
// resets attributes to match its OWN render regardless of
// `suppressHydrationWarning` — that flag only silences the console warning
// for TEXT-content mismatches, not attribute reconciliation. Confirmed live
// in a real production build: removing `suppressHydrationWarning` surfaced
// React error #418 (hydration failed on <html>) on every load, and
// restoring it made the error silent but the attribute still got wiped —
// proving React was reconciling it away either way, not merely warning.
//
// Reading the cookie server-side removes the mismatch structurally: the
// attribute IS what the server rendered, so client and server agree from
// the first frame, no script-timing race and nothing to reconcile.
const THEME_COOKIE = "thesistrace-theme";

// Story 11.1 (Epic 11, Instrument Panel): JetBrains Mono is the primary read
// face, not a code-only accent — every weight the report actually uses.
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ThesisTrace",
  description: "Evidence-backed equity intelligence — deterministic forensic scores with provenance.",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const cookieStore = await cookies();
  const theme = cookieStore.get(THEME_COOKIE)?.value === "light" ? "light" : "dark";

  return (
    <html lang="en" className={jetbrainsMono.variable} data-theme={theme}>
      <body>
        <header className="sticky top-0 z-10 border-b border-[var(--color-border-strong)] bg-[var(--color-surface)]/90 backdrop-blur">
          <div className="mx-auto flex min-w-0 max-w-5xl items-center justify-between px-3 py-4 sm:px-6">
            <Link href="/" className="flex min-w-0 items-baseline gap-1 no-underline sm:gap-2">
              <span className="text-title font-bold uppercase tracking-[var(--tracking-label)] text-[var(--color-ink)]">
                ThesisTrace
              </span>
              <span className="hidden text-caption uppercase tracking-[var(--tracking-label)] text-[var(--color-ink-faint)] sm:inline">
                evidence-backed equity intelligence
              </span>
            </Link>
            <nav className="flex shrink-0 items-center gap-1 text-caption font-medium uppercase tracking-[var(--tracking-label)] text-[var(--color-ink-muted)] sm:gap-5">
              <Link href="/" className="whitespace-nowrap transition-colors hover:text-[var(--color-brand-500)]">
                Companies
              </Link>
              <Link
                href="/architecture"
                className="whitespace-nowrap transition-colors hover:text-[var(--color-brand-500)]"
              >
                Architecture
              </Link>
              <ThemeToggle initialTheme={theme} />
            </nav>
          </div>
        </header>
        {/* No max-width here — content width varies by page (data-dense pages
            run wider, prose-heavy pages stay at a comfortable reading measure)
            per DESIGN.md's Layout & Spacing. Each page's own <main> sets it. */}
        <div className="px-6 py-10">{children}</div>
        <footer className="border-t border-[var(--color-border)] bg-[var(--color-surface)]">
          <div className="mx-auto max-w-5xl px-6 py-6 text-xs leading-relaxed text-[var(--color-ink-faint)]">
            ThesisTrace presents evidence-based analytical scores computed from public SEC EDGAR
            filings. It is not investment, legal, or tax advice, and nothing on this site is a
            recommendation to buy, sell, or hold any security. Scores are derived from historical
            filings and may not reflect a company&apos;s current financial condition. Do your own
            research and consult a licensed financial advisor before making investment decisions.
          </div>
        </footer>
      </body>
    </html>
  );
}
