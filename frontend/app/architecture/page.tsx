// Architecture page — renders the Mermaid diagram suite in-app.
//
// Single source of truth: the diagram sources are READ FROM docs/diagrams/*.md at
// build time, never copied into this file. Editing a diagram in docs/ updates the
// page, so the documentation and the app cannot drift apart.
//
// Note this reads from OUTSIDE frontend/. On Vercel that requires the project's
// "Include files outside the root directory" setting to stay enabled (it is on by
// default for monorepos). A missing file fails the build loudly rather than
// rendering a blank page.

import fs from "node:fs/promises";
import path from "node:path";

import { Card } from "../components/ui/Card";
import { MermaidDiagram } from "../components/MermaidDiagram";

// Static content — read once at build time.
export const dynamic = "force-static";

export const metadata = {
  title: "Architecture — ThesisTrace",
  description:
    "How ThesisTrace is built: the read path, the deterministic scoring pipeline, and the explanation lifecycle.",
};

const DIAGRAMS_DIR = path.join(process.cwd(), "..", "docs", "diagrams");

const FILES = [
  "01-system-architecture.md",
  "03-data-pipeline.md",
  "05-explanation-lifecycle.md",
] as const;

type Diagram = {
  slug: string;
  title: string;
  /** Lead-in prose between the H1 and the diagram, as paragraphs. */
  intro: string[];
  chart: string;
};

/** Pull the H1, the lead-in paragraphs, and the first ```mermaid block out of a doc. */
function parseDiagramDoc(source: string, slug: string): Diagram | null {
  const fence = source.match(/```mermaid\n([\s\S]*?)\n```/);
  if (!fence) return null;

  const title = source.match(/^#\s+(.+)$/m)?.[1]?.trim() ?? slug;

  const beforeFence = source.slice(0, fence.index ?? 0);
  const intro = beforeFence
    .replace(/^#\s+.+$/m, "")
    .split(/\n{2,}/)
    .map((p) => p.replace(/\s+/g, " ").trim())
    // Strip the markdown bold markers; this page renders plain text, not markdown.
    .map((p) => p.replace(/\*\*(.+?)\*\*/g, "$1"))
    .filter(Boolean);

  return { slug, title, intro, chart: fence[1] };
}

async function loadDiagrams(): Promise<Diagram[]> {
  const docs = await Promise.all(
    FILES.map(async (file) => {
      const source = await fs.readFile(path.join(DIAGRAMS_DIR, file), "utf8");
      return parseDiagramDoc(source, file.replace(/\.md$/, ""));
    })
  );
  return docs.filter((d): d is Diagram => d !== null);
}

export default async function ArchitecturePage() {
  const diagrams = await loadDiagrams();

  return (
    // Wider than the prose pages — these diagrams are data-dense, per DESIGN.md's
    // Layout & Spacing note that content width varies by page.
    <main className="mx-auto w-full max-w-7xl space-y-8">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-ink)]">
          Architecture
        </h1>
        <p className="max-w-2xl text-[var(--color-ink-muted)]">
          How ThesisTrace is built. Every label below traces to a real file, route, table, or
          data provider in the codebase — these diagrams are generated from the source, not
          drawn by hand.
        </p>
      </header>

      <Card>
        <h2 className="text-sm font-semibold text-[var(--color-ink)]">The core invariant</h2>
        <p className="mt-2 text-sm leading-relaxed text-[var(--color-ink-muted)]">
          Every score and number is computed deterministically in Python on a scheduled batch
          run, before any request arrives. The language model only rewrites already-final
          prose, and only when explicitly asked. It never originates a figure.
        </p>
      </Card>

      {diagrams.map((d, i) => (
        <section key={d.slug} className="space-y-3">
          <div className="space-y-2">
            <h2 className="text-lg font-semibold tracking-tight text-[var(--color-ink)]">
              {i + 1}. {d.title}
            </h2>
            {d.intro.map((p, j) => (
              <p key={j} className="max-w-2xl text-sm leading-relaxed text-[var(--color-ink-muted)]">
                {p}
              </p>
            ))}
          </div>
          <Card className="p-4">
            <MermaidDiagram id={`diagram-${d.slug}`} chart={d.chart} />
          </Card>
          <p className="text-xs text-[var(--color-ink-faint)]">
            Source: <code>docs/diagrams/{d.slug}.md</code> — that file also carries the
            supporting tables (deployment status, endpoint list, degradation rules).
          </p>
        </section>
      ))}

      {diagrams.length === 0 && (
        <Card>
          <p className="text-[var(--color-ink-muted)]">No diagrams found.</p>
        </Card>
      )}
    </main>
  );
}
