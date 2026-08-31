// Inline term-definition primitive (Story 11.5, new capability). A single
// reusable component so Story 11.7 can wire it into every model's signal
// table without reimplementing the interaction (AC).
//
// A real <button>, not a styled <span onClick>, because native button
// semantics are what makes "focusable, expandable via Enter/Space, not
// click-only" true for free — the browser fires a click event for both a
// mouse click and Enter/Space on a real button, so one onClick handler
// covers both input methods correctly rather than us reimplementing key
// handling (and getting it half-right, the way ARIA widgets often do).
//
// Expand/collapse animates via a grid-template-rows 0fr->1fr transition
// (no JS height measurement needed) gated behind Tailwind's `motion-safe:`
// variant, which maps directly to `prefers-reduced-motion: no-preference` —
// under reduced motion the row still resizes, just without an animated
// transition, so content is never permanently hidden either way.
//
// The definition panel is `display: grid` (block-level), so it is a block
// box sitting inside an inline ancestor — any sibling text placed AFTER a
// <Term> in the same paragraph gets pushed onto a new line below the
// (possibly collapsed) panel, by ordinary block-in-inline layout rules, not
// a bug in this component. Prefer ending a sentence AT the term rather than
// following it with more inline text/punctuation in the same paragraph.
"use client";

import { useId, useState } from "react";
import { TERM_DEFINITIONS, type TermId } from "./termDefinitions";

export function Term({ id, children }: { id: TermId; children: React.ReactNode }) {
  const [expanded, setExpanded] = useState(false);
  const definitionId = useId();

  return (
    <span>
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
        aria-controls={definitionId}
        style={{ font: "inherit" }}
        className="cursor-help border-0 border-b border-dashed border-[var(--color-brand-link)] bg-transparent p-0 text-[var(--color-brand-link)] transition-colors hover:text-[var(--color-brand-link-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-brand-link)] focus-visible:outline-offset-2"
      >
        {children}
      </button>
      <span
        id={definitionId}
        role="note"
        aria-hidden={!expanded}
        className={`grid overflow-hidden motion-safe:transition-[grid-template-rows] motion-safe:duration-200 motion-safe:ease-out ${
          expanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <span className="block overflow-hidden pt-1 text-caption leading-relaxed text-[var(--color-ink-faint)]">
          {TERM_DEFINITIONS[id]}
        </span>
      </span>
    </span>
  );
}
