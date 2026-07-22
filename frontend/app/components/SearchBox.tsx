"use client";

// Ticker search (FR-2). Navigates to the company page, which itself renders an
// honest "not yet covered" for anything outside the universe (AD-10).
import { useRouter } from "next/navigation";
import { useState } from "react";
import { SearchIcon } from "./ui/icons";
import { Button } from "./ui/Button";

export default function SearchBox() {
  const router = useRouter();
  const [ticker, setTicker] = useState("");

  function go(e: React.FormEvent) {
    e.preventDefault();
    const t = ticker.trim().toUpperCase();
    if (t) router.push(`/company/${encodeURIComponent(t)}`);
  }

  return (
    <form onSubmit={go} className="flex max-w-md items-center gap-2 pt-1">
      <div className="relative flex-1">
        <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-ink-faint)]" />
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="Search a ticker (e.g. SHOP)"
          aria-label="Ticker search"
          className="w-full rounded-[var(--radius-control)] border border-[var(--color-border-strong)] bg-[var(--color-surface)] py-2.5 pl-9 pr-3 text-sm text-[var(--color-ink)] outline-none placeholder:text-[var(--color-ink-faint)] focus:border-[var(--color-brand-500)] focus:ring-2 focus:ring-[var(--color-brand-100)]"
        />
      </div>
      <Button type="submit">Search</Button>
    </form>
  );
}
