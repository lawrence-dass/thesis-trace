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

// Architecture sources intentionally keep their authored light palette in
// docs/diagrams/*.md. Mermaid classDef colors override Mermaid's base theme,
// so map that known palette to dark equivalents at the rendering boundary.
// This keeps the source diagrams readable as standalone documentation while
// ensuring the in-app dark-first theme does not produce pale panels on a dark
// canvas.
const DARK_PALETTE: Array<[string, string]> = [
  ["#F3E8FF", "#2d2140"],
  ["#7E22CE", "#b48ee0"],
  ["#3B0764", "#f0e8ff"],
  ["#DBEAFE", "#1d3154"],
  ["#2563EB", "#7ca4ff"],
  ["#1E3A8A", "#e4edff"],
  ["#DCFCE7", "#17392d"],
  ["#16A34A", "#3ddc97"],
  ["#14532D", "#e0fff1"],
  ["#FEF3C7", "#3b2f1a"],
  ["#D97706", "#e8a83c"],
  ["#78350F", "#fff3d6"],
  ["#FFF7ED", "#3d281b"],
  ["#EA580C", "#ff8a5e"],
  ["#9A3412", "#ffe9de"],
  ["#FCE7F3", "#3d2432"],
  ["#DB2777", "#ff7eb0"],
  ["#831843", "#ffe7f1"],
  ["#E0F2FE", "#17384a"],
  ["#0284C7", "#6bd6ff"],
  ["#0C4A6E", "#e4f8ff"],
  ["#EDE9FE", "#30214a"],
  ["#7C3AED", "#c39bff"],
  ["#4C1D95", "#f2e8ff"],
];

function chartForTheme(chart: string, theme: "dark" | "light") {
  if (theme === "light") return chart;
  return DARK_PALETTE.reduce((source, [light, dark]) => source.replaceAll(light, dark), chart);
}

export function MermaidDiagram({ id, chart }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<State>("loading");
  const [message, setMessage] = useState<string>("");
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  // Default to fit so the whole shape is visible on arrival; actual size is one
  // click away for reading the labels.
  const [fit, setFit] = useState(true);

  useEffect(() => {
    const readTheme = () => {
      setTheme(document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark");
    };
    readTheme();

    const observer = new MutationObserver(readTheme);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    setMessage("");
    if (ref.current) ref.current.innerHTML = "";

    async function render() {
      try {
        const { default: mermaid } = await import("mermaid");
        if (cancelled) return;

        mermaid.initialize({
          startOnLoad: false,
          theme: theme === "dark" ? "dark" : "default",
          // The diagrams carry their own classDef palette; dark mode receives
          // the equivalent palette through chartForTheme below.
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

        const { svg } = await mermaid.render(id, chartForTheme(chart, theme));
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
  }, [id, chart, theme]);

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
