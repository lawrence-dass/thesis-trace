"use client";

// Ticker search (FR-2). Navigates to the company page, which itself renders an
// honest "not yet covered" for anything outside the universe (AD-10).
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function SearchBox() {
  const router = useRouter();
  const [ticker, setTicker] = useState("");

  function go(e: React.FormEvent) {
    e.preventDefault();
    const t = ticker.trim().toUpperCase();
    if (t) router.push(`/company/${encodeURIComponent(t)}`);
  }

  return (
    <form onSubmit={go} style={{ margin: "1rem 0" }}>
      <input
        value={ticker}
        onChange={(e) => setTicker(e.target.value)}
        placeholder="Search a ticker (e.g. SHOP)"
        aria-label="Ticker search"
        style={{ padding: "0.5rem", fontSize: "1rem", width: 240 }}
      />
      <button type="submit" style={{ padding: "0.5rem 1rem", marginLeft: 8 }}>
        Search
      </button>
    </form>
  );
}
