// Skeleton landing page (Story 1.1): proves the frontend -> backend wire only.
// This is NOT FR-1 (the Company Universe starter list) — that lands in Story 4.1.
// Presentation only; contains no scoring/canonicalization logic (AD-8).

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function getBackendHealth(): Promise<"ok" | "unreachable"> {
  try {
    const res = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
    if (!res.ok) return "unreachable";
    const body = (await res.json()) as { status?: string };
    return body.status === "ok" ? "ok" : "unreachable";
  } catch {
    return "unreachable";
  }
}

export default async function Home() {
  const backend = await getBackendHealth();
  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: 640 }}>
      <h1>ThesisTrace</h1>
      <p>Evidence-backed equity intelligence. Deterministic forensic scores with provenance.</p>
      <p>
        backend: <strong>{backend}</strong>
      </p>
    </main>
  );
}
