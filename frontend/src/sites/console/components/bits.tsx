import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { inrLakh, istClock, istDateTime } from "../../../shared/format";
import {
  EmptyState as SharedEmptyState,
  ErrorNotice as SharedErrorNotice,
} from "../../../shared/components/notices";

/** ₹ lakh formatting for a single CTC figure (null → null). Thin re-export of
 *  the shared `inrLakh` (single source in shared/format.ts) for the recruiter
 *  surfaces — Postings list, composer preview, dashboard. */
export const lakh = inrLakh;

/** The "₹xL – ₹yL" / "Undisclosed" compensation band as a plain string. */
export function ctcBandText(min: number | null, max: number | null): string {
  const lo = lakh(min);
  const hi = lakh(max);
  if (!lo && !hi) return "Undisclosed";
  return [lo, hi].filter(Boolean).join(" – ");
}

/** Live IST clock — the control-room heartbeat in the masthead (Asia/Kolkata). */
export function IstClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return <span className="clock num">{istClock(now)}</span>;
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span className="k">{label}</span>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </label>
  );
}

/** Compact relative + absolute timestamp. */
export function Stamp({ iso }: { iso: string }) {
  const date = new Date(iso);
  const deltaMs = Date.now() - date.getTime();
  const minutes = Math.round(Math.abs(deltaMs) / 60_000);
  const rel =
    minutes < 1
      ? "now"
      : minutes < 60
        ? `${minutes}m`
        : minutes < 60 * 48
          ? `${Math.round(minutes / 60)}h`
          : `${Math.round(minutes / 1440)}d`;
  const sign = rel === "now" ? "now" : deltaMs >= 0 ? `${rel} ago` : `in ${rel}`;
  return (
    <span className="num" title={`${date.toISOString()} (UTC)`}>
      <span className="dim">{istDateTime(iso)} IST</span>{" "}
      <span>· {sign}</span>
    </span>
  );
}

export function ShortId({ id, onPick }: { id: string; onPick?: (id: string) => void }) {
  const short = `${id.slice(0, 8)}…${id.slice(-4)}`;
  if (!onPick) {
    return (
      <span className="num" title={id}>
        {short}
      </span>
    );
  }
  return (
    <span
      className="num clickable-id"
      title={`${id} — click to use in user actions`}
      onClick={(e) => {
        e.stopPropagation();
        onPick(id);
      }}
    >
      {short}
    </span>
  );
}

export function JsonView({ value }: { value: unknown }) {
  return <pre className="json-view">{JSON.stringify(value, null, 2)}</pre>;
}

export function Drawer({
  title,
  onClose,
  children,
  foot,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  foot?: ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <>
      <div className="drawer-veil" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label={title}>
        <div className="drawer-head">
          <h2>{title}</h2>
          <button className="btn ghost sm" onClick={onClose}>
            ESC / Close
          </button>
        </div>
        <div className="drawer-body">{children}</div>
        {foot && <div className="drawer-foot">{foot}</div>}
      </aside>
    </>
  );
}

export function ErrorNotice({ error }: { error: string | null }) {
  return <SharedErrorNotice error={error} className="notice error" />;
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <SharedEmptyState as="div" innerClassName="flavor">
      {children}
    </SharedEmptyState>
  );
}

export function ScoreBar({ score }: { score: number | null }) {
  if (score === null) return <span className="dim">—</span>;
  return (
    <span className="scorebar">
      <span className="track">
        <span className="fill" style={{ width: `${Math.round(score * 100)}%` }} />
      </span>
      <span className="num">{score.toFixed(2)}</span>
    </span>
  );
}
