import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-[50vh] max-w-5xl flex-col items-center justify-center gap-4 text-center">
      <p className="font-mono text-sm font-semibold text-[var(--color-brand-link)]">404</p>
      <h1 className="text-headline font-semibold text-[var(--color-ink)]">Page not found</h1>
      <p className="max-w-md text-[var(--color-ink-muted)]">
        The page you requested does not exist or is no longer available.
      </p>
      <Link
        href="/"
        className="text-sm font-medium text-[var(--color-brand-link)] underline-offset-4 hover:text-[var(--color-brand-link-hover)] hover:underline"
      >
        Return to companies
      </Link>
    </main>
  );
}
