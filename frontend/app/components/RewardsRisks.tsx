// Rewards and risks (Story 10.3, D12). Renders exactly what the read API
// returns — a SELECTION of already-computed bands and open data-quality
// issues, never a new figure, never free prose, never an LLM (AD-8). Every
// item's `attribution` says whose selection this is; this component trusts
// the API for that text rather than asserting its own.

import { Badge } from "./ui/Badge";

export type RewardRiskItem = {
  kind: "reward" | "risk";
  text: string;
  section: string;
  model: string | null;
  fiscal_year: number | null;
  accession_number: string | null;
  attribution: string;
  spec_version: string;
};

function List({ items, emptyLabel }: { items: RewardRiskItem[]; emptyLabel: string }) {
  if (items.length === 0) {
    return <p className="text-sm text-[var(--color-ink-faint)]">{emptyLabel}</p>;
  }
  return (
    <ul className="space-y-2">
      {items.map((item, i) => (
        <li key={i}>
          <a
            href={`#${item.section}`}
            className="block rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-sm text-[var(--color-ink)] no-underline transition-colors hover:border-[var(--color-border-strong)]"
          >
            {item.text}
          </a>
        </li>
      ))}
    </ul>
  );
}

export function RewardsRisks({ items }: { items: RewardRiskItem[] }) {
  // The API schema rejects unknown kinds, but keep this component fail-closed
  // because the page consumes JSON via a type assertion rather than a runtime
  // validator. An invalid item must not turn into two misleading "None"
  // states.
  const recognized = items.filter((item) => item.kind === "reward" || item.kind === "risk");
  const rewards = recognized.filter((i) => i.kind === "reward");
  const risks = recognized.filter((i) => i.kind === "risk");

  // Honest empty state (AD-16): a company with nothing qualifying gets one
  // plain note, not two empty lists each padded with a heading and nothing
  // beneath it.
  if (recognized.length === 0) {
    return (
      <p className="text-sm text-[var(--color-ink-faint)]">
        No standout rewards or risks in this company&apos;s current classifications.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Badge variant="pass" icon={false}>
            Rewards
          </Badge>
          <List items={rewards} emptyLabel="None currently." />
        </div>
        <div className="space-y-2">
          <Badge variant="fail" icon={false}>
            Risks
          </Badge>
          <List items={risks} emptyLabel="None currently." />
        </div>
      </div>
      <p className="text-xs leading-relaxed text-[var(--color-ink-faint)]">{recognized[0].attribution}</p>
    </div>
  );
}
