import Link from "next/link";
import type { ReactNode } from "react";

type CardProps = {
  children: ReactNode;
  className?: string;
  href?: string;
  highlight?: boolean;
};

const BASE =
  "block rounded-[var(--radius-card)] border bg-[var(--color-surface)] p-5 shadow-[var(--shadow-card)] transition-all";

export function Card({ children, className = "", href, highlight = false }: CardProps) {
  const border = highlight ? "border-[var(--color-brand-500)]" : "border-[var(--color-border)]";
  const classes = `${BASE} ${border} ${className}`;

  if (href) {
    return (
      <Link href={href} className={`${classes} no-underline hover:shadow-[var(--shadow-card-hover)] hover:border-[var(--color-border-strong)]`}>
        {children}
      </Link>
    );
  }
  return <div className={classes}>{children}</div>;
}
