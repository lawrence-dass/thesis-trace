import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost";

const VARIANT_CLASS: Record<Variant, string> = {
  primary:
    "bg-[var(--color-brand-600)] text-white border-transparent hover:bg-[var(--color-brand-700)]",
  secondary:
    "bg-[var(--color-surface)] text-[var(--color-ink)] border-[var(--color-border-strong)] hover:bg-[var(--color-canvas)]",
  ghost:
    "bg-transparent text-[var(--color-ink-muted)] border-transparent hover:text-[var(--color-ink)]",
};

const BASE =
  "inline-flex items-center justify-center gap-2 rounded-[var(--radius-control)] border px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 no-underline";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return <button className={`${BASE} ${VARIANT_CLASS[variant]} ${className}`} {...props} />;
}

export function LinkButton({
  href,
  variant = "primary",
  className = "",
  children,
}: {
  href: string;
  variant?: Variant;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Link href={href} className={`${BASE} ${VARIANT_CLASS[variant]} ${className}`}>
      {children}
    </Link>
  );
}
