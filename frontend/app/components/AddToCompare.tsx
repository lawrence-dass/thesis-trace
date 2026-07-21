"use client";

// Add-to-comparison (FR-13): session-only set (no auth, no server persistence),
// min 2 / max 4. Persisted in sessionStorage; links to the compare view.
import { useEffect, useState } from "react";

const KEY = "thesistrace.compare";
const MAX = 4;

function read(): string[] {
  try {
    return JSON.parse(sessionStorage.getItem(KEY) ?? "[]") as string[];
  } catch {
    return [];
  }
}

export default function AddToCompare({ ticker }: { ticker: string }) {
  const [set, setSet] = useState<string[]>([]);

  useEffect(() => setSet(read()), []);

  function toggle() {
    const current = read();
    let next: string[];
    if (current.includes(ticker)) {
      next = current.filter((t) => t !== ticker);
    } else if (current.length >= MAX) {
      return; // cap at 4
    } else {
      next = [...current, ticker];
    }
    sessionStorage.setItem(KEY, JSON.stringify(next));
    setSet(next);
  }

  const inSet = set.includes(ticker);
  return (
    <div style={{ margin: "1rem 0" }}>
      <button onClick={toggle} disabled={!inSet && set.length >= MAX}>
        {inSet ? "Remove from comparison" : "Add to comparison"}
      </button>
      {set.length >= 2 ? (
        <a href={`/compare?tickers=${set.join(",")}`} style={{ marginLeft: 12 }}>
          Compare {set.length} →
        </a>
      ) : (
        <span style={{ marginLeft: 12, color: "#666" }}>Add at least 2 to compare (max 4).</span>
      )}
    </div>
  );
}
