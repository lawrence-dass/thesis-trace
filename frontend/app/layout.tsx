import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Inter } from "next/font/google";
import Link from "next/link";
import Script from "next/script";
import { ThemeToggle } from "./components/ThemeToggle";
import "./globals.css";

// Sets `data-theme` before first paint so the dark-primary default (D12)
// never flashes light for a returning visitor who chose it. `beforeInteractive`
// is Next's documented mechanism for exactly this — code that must run before
// hydration — and Next hoists it into <head> regardless of where the
// component sits in the tree. Defaults to "dark" on any failure (private
// browsing, storage blocked), matching the site's primary theme.
const THEME_INIT_SCRIPT = `
  (function () {
    try {
      var stored = window.localStorage.getItem("thesistrace-theme");
      document.documentElement.setAttribute("data-theme", stored === "light" ? "light" : "dark");
    } catch (e) {
      document.documentElement.setAttribute("data-theme", "dark");
    }
  })();
`;

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: "ThesisTrace",
  description: "Evidence-backed equity intelligence — deterministic forensic scores with provenance.",
};

// suppressHydrationWarning below is scoped to <html> only (React does not
// propagate it to children) and is the documented fix for exactly this case:
// `data-theme` is set by the blocking script further down, outside React's
// render, before hydration — so the attribute React sees on mount
// legitimately differs from what it rendered on the server. Same technique
// next-themes uses; without it, every load logs a spurious hydration-mismatch
// warning that has nothing to do with an actual bug.
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body>
        <Script id="theme-init" strategy="beforeInteractive">
          {THEME_INIT_SCRIPT}
        </Script>
        <header className="sticky top-0 z-10 border-b border-[var(--color-border)] bg-[var(--color-surface)]/90 backdrop-blur">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
            <Link href="/" className="flex items-baseline gap-2 no-underline">
              <span className="text-lg font-semibold tracking-tight text-[var(--color-ink)]">ThesisTrace</span>
              <span className="hidden text-xs font-medium text-[var(--color-ink-faint)] sm:inline">
                evidence-backed equity intelligence
              </span>
            </Link>
            <nav className="flex items-center gap-5 text-sm font-medium text-[var(--color-ink-muted)]">
              <Link href="/" className="transition-colors hover:text-[var(--color-ink)]">
                Companies
              </Link>
              <Link href="/architecture" className="transition-colors hover:text-[var(--color-ink)]">
                Architecture
              </Link>
              <ThemeToggle />
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
