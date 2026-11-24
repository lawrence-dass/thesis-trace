"use client";

// Shown only when the data cache holds NO copy of a page's data yet and the read
// API is unreachable: once a response is cached it keeps being served through
// any later outage (app/lib/api.ts). The usual cause is the free-tier API waking from
// sleep (~45s), so the action offered is a retry, not a dead end.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { startTransition } from "react";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const router = useRouter();
  // reset() alone only re-renders on the client; the failure was in a server
  // component, so the server render has to be re-requested too.
  const retry = () =>
    startTransition(() => {
      router.refresh();
      reset();
    });

  return (
    <main className="mx-auto flex min-h-[50vh] max-w-5xl flex-col items-center justify-center gap-4 text-center">
      <p className="font-mono text-sm font-semibold text-[var(--color-brand-link)]">Data service waking up</p>
      <h1 className="text-headline font-semibold text-[var(--color-ink)]">This report isn&apos;t ready yet</h1>
      <p className="max-w-md text-[var(--color-ink-muted)]">
        The ThesisTrace data service is starting up. This usually takes under a minute.
      </p>
      <div className="flex items-center gap-6">
        <button
          type="button"
          onClick={retry}
          className="text-sm font-medium text-[var(--color-brand-link)] underline-offset-4 hover:text-[var(--color-brand-link-hover)] hover:underline"
        >
          Try again
        </button>
        <Link
          href="/"
          className="text-sm font-medium text-[var(--color-ink-muted)] underline-offset-4 hover:underline"
        >
          Return to companies
        </Link>
      </div>
    </main>
  );
}
