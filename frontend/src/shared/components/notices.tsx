import type { ElementType, ReactNode } from "react";

/**
 * Canonical inline error + empty-state primitives shared by the web and console
 * surfaces. Markup is intentionally configurable: each surface relies on its own
 * `.surface-*`-scoped CSS (web: `.notice.err` + `.empty .serif`; console:
 * `.notice.error` + `.empty .flavor`), so the className/tag are passed in by the
 * per-surface thin wrappers rather than hardcoded here. The shared logic is the
 * null-guard and the wrapper structure.
 */

export function ErrorNotice({ error, className }: { error: string | null; className: string }) {
  if (!error) return null;
  return <div className={className}>⚠ {error}</div>;
}

export function EmptyState({
  children,
  as: As,
  innerClassName,
}: {
  children: ReactNode;
  as: ElementType;
  innerClassName: string;
}) {
  return (
    <div className="empty">
      <As className={innerClassName}>{children}</As>
    </div>
  );
}
