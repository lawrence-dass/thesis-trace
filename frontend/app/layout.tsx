import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Inter } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: "ThesisTrace",
  description: "Evidence-backed equity intelligence — deterministic forensic scores with provenance.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
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
            </nav>
          </div>
        </header>
        <div className="mx-auto max-w-5xl px-6 py-10">{children}</div>
      </body>
    </html>
  );
}
