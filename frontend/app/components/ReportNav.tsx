"use client";

// Persistent section nav for the report-style company page (Story 10.1,
// D12). Highlights whichever section is currently under the sticky header
// via IntersectionObserver; the jump itself is plain <a href="#id">
// anchors plus `scroll-behavior: smooth` in globals.css, so navigation
// keeps working with JS disabled and the URL hash stays the source of
// truth for "which section" (satisfies "addressable by a stable URL
// anchor" without any client-side routing).

import { useEffect, useState } from "react";

export type ReportSection = { id: string; label: string };

export function ReportNav({ sections }: { sections: ReportSection[] }) {
  const [active, setActive] = useState(sections[0]?.id ?? "");

  useEffect(() => {
    const targets = sections
      .map((s) => document.getElementById(s.id))
      .filter((el): el is HTMLElement => el !== null);
    if (targets.length === 0) return;

    // Treat the band just below the sticky header+nav as "current" — a
    // section counts as active once its heading crosses that line, not
    // only while fully in view, which is what lets the LAST section become
    // active even though it can never fill 60%+ of a tall viewport.
    const observer = new IntersectionObserver(
      (entries) => {
        setActive((current) => {
          const intersecting = entries.filter((e) => e.isIntersecting);
          if (intersecting.length === 0) return current;
          const topmost = intersecting.reduce((a, b) =>
            a.boundingClientRect.top < b.boundingClientRect.top ? a : b,
          );
          return topmost.target.id;
        });
      },
      { rootMargin: "-112px 0px -60% 0px", threshold: 0 },
    );
    targets.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [sections]);

  return (
    <nav
      aria-label="Report sections"
      className="sticky top-[65px] z-[9] -mx-6 border-b border-[var(--color-border)] bg-[var(--color-surface)]/90 px-6 backdrop-blur"
    >
      <ul className="mx-auto flex w-full max-w-7xl gap-1 overflow-x-auto">
        {sections.map((s) => (
          <li key={s.id}>
            <a
              href={`#${s.id}`}
              aria-current={active === s.id ? "true" : undefined}
              className={`inline-block whitespace-nowrap border-b-2 px-3 py-3 text-sm font-medium transition-colors ${
                active === s.id
                  ? "border-[var(--color-brand-500)] text-[var(--color-ink)]"
                  : "border-transparent text-[var(--color-ink-faint)] hover:text-[var(--color-ink)]"
              }`}
            >
              {s.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
