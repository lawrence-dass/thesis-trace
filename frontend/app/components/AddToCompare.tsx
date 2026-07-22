"use client";

// Add-to-comparison (FR-13): session-only set (no auth, no server persistence),
// min 2 / max 4. Persisted in sessionStorage; links to the compare view.
import { useEffect, useState } from "react";
import { Button, LinkButton } from "./ui/Button";
import { ArrowRightIcon } from "./ui/icons";

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
    <div className="flex items-center gap-3">
      <Button variant={inSet ? "secondary" : "primary"} onClick={toggle} disabled={!inSet && set.length >= MAX}>
        {inSet ? "Remove from comparison" : "Add to comparison"}
      </Button>
      {set.length >= 2 ? (
        <LinkButton href={`/compare?tickers=${set.join(",")}`} variant="ghost">
          Compare {set.length}
          <ArrowRightIcon className="h-3.5 w-3.5" />
        </LinkButton>
      ) : (
        <span className="text-xs text-[var(--color-ink-faint)]">Add at least 2 to compare (max 4).</span>
      )}
    </div>
  );
}
