// Methodology page per score (FR-11): formula, inputs, version, cited source.
// Presentation only — renders exactly what the read API returns (AD-8).

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Signal = { key: string; description: string };
type Methodology = {
  state: string;
  model?: string;
  formula_version?: string;
  description?: string;
  inputs?: string[];
  signals?: Signal[];
  source?: string;
  threshold?: Record<string, unknown> | null;
};

async function getMethodology(model: string): Promise<Methodology> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/methodology/${model}`, { cache: "no-store" });
    return (await res.json()) as Methodology;
  } catch {
    return { state: "unreachable" };
  }
}

export default async function MethodologyPage({ params }: { params: Promise<{ model: string }> }) {
  const { model } = await params;
  const m = await getMethodology(model);

  if (m.state !== "ok") {
    return (
      <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
        <h1>{model}</h1>
        <p>{m.state === "not_available" ? "No methodology for this model." : "Backend unreachable."}</p>
      </main>
    );
  }

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: 760 }}>
      <h1>Methodology — {m.model}</h1>
      <p>
        <strong>Formula version:</strong> {m.formula_version}
      </p>
      <p>{m.description}</p>
      <h2>Inputs (canonical concepts)</h2>
      <ul>{m.inputs?.map((i) => <li key={i}>{i}</li>)}</ul>
      <h2>Signals</h2>
      <ul>
        {m.signals?.map((s) => (
          <li key={s.key}>
            <strong>{s.key}</strong>: {s.description}
          </li>
        ))}
      </ul>
      {m.source ? (
        <p>
          <strong>Source:</strong> {m.source}
        </p>
      ) : null}
    </main>
  );
}
