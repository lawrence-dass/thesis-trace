// Renders a Mermaid diagram source string to inline SVG on the client.
//
// `mermaid` is ~2MB, so it is loaded with a dynamic import — it stays out of the
// main bundle and is only fetched on pages that actually draw a diagram.
// Presentation only: the diagram source is authored in docs/diagrams/*.md and
// passed in by the server component, never constructed here.

"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  /** Unique per rendered diagram — Mermaid uses it as the generated SVG's DOM id. */
  id: string;
  /** Raw Mermaid source, exactly as it appears inside the ```mermaid fence. */
  chart: string;
};

type State = "loading" | "ready" | "error";

export function MermaidDiagram({ id, chart }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<State>("loading");
  const [message, setMessage] = useState<string>("");
  // Default to fit so the whole shape is visible on arrival; actual size is one
  // click away for reading the labels.
  const [fit, setFit] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function render() {
      try {
        const { default: mermaid } = await import("mermaid");
        if (cancelled) return;

        mermaid.initialize({
          startOnLoad: false,
          theme: "default",
          // The diagrams carry their own classDef palette, so the base theme only
          // needs to supply typography and a transparent canvas.
          themeVariables: {
            fontFamily: "var(--font-inter), system-ui, sans-serif",
            fontSize: "14px",
            background: "transparent",
          },
          // Always render at native size; the "fit" view scales the finished SVG
          // with CSS instead. Doing it that way means toggling between fit and
          // actual size costs nothing — no re-render, no second layout pass.
          flowchart: { useMaxWidth: false, htmlLabels: true },
          sequence: { useMaxWidth: false },
        });

        const { svg } = await mermaid.render(id, chart);
        if (cancelled || !ref.current) return;
        ref.current.innerHTML = svg;
        setState("ready");
      } catch (err) {
        if (cancelled) return;
        // Surface the failure rather than leaving an empty box — a diagram that
        // silently doesn't render looks identical to one that isn't there.
        setMessage(err instanceof Error ? err.message : "Unknown rendering error.");
        setState("error");
      }
    }

    render();
    return () => {
      cancelled = true;
    };
  }, [id, chart]);

  if (state === "error") {
    return (
      <div className="rounded-[var(--radius-control)] border border-[var(--color-signal-fail-border)] bg-[var(--color-signal-fail-bg)] p-4">
        <p className="text-sm font-medium text-[var(--color-signal-fail)]">
          This diagram could not be rendered.
        </p>
        <p className="mt-1 text-xs text-[var(--color-ink-muted)]">{message}</p>
      </div>
    );
  }

  return (
    <figure className="m-0 space-y-2">
      <figcaption className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={() => setFit((f) => !f)}
          aria-pressed={!fit}
          disabled={state !== "ready"}
          className="rounded-[var(--radius-chip)] border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1 text-xs font-medium text-[var(--color-ink-muted)] transition-colors hover:border-[var(--color-border-strong)] hover:text-[var(--color-ink)] disabled:opacity-0"
        >
          {fit ? "Actual size" : "Fit to width"}
        </button>
      </figcaption>

      <div className={fit ? "" : "overflow-x-auto"}>
        {state === "loading" && (
          <p className="py-8 text-sm text-[var(--color-ink-faint)]">Rendering diagram…</p>
        )}
        <div
          ref={ref}
          className={
            // max-w (not w) so a diagram narrower than the container keeps its
            // native size instead of being upscaled — upscaling the tall, narrow
            // pipeline diagram only makes it taller without adding legibility.
            fit
              ? "[&_svg]:h-auto [&_svg]:max-w-full"
              : "[&_svg]:h-auto [&_svg]:max-w-none"
          }
        />
      </div>

      {state === "ready" && fit && (
        <p className="text-xs text-[var(--color-ink-faint)]">
          Scaled to fit. Switch to actual size to read the labels, then scroll sideways.
        </p>
      )}
    </figure>
  );
}
