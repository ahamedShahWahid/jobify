/* Jobify is an India-first product: timestamps are stored and transported in UTC
 * (never localize storage), but every *displayed* time is Indian Standard Time
 * (Asia/Kolkata, UTC+5:30) and money uses Indian conventions (₹, lakh, the
 * 2,3-digit grouping). This module is the single source for both. */

export const IST_TZ = "Asia/Kolkata";

/* Intl formatters are expensive to construct (locale-data parsing), so build
 * them once at module load and reuse — these render on hot paths (the console
 * clock ticks every second; stamps render per audit/log row). */
const IST_DATETIME_FMT = new Intl.DateTimeFormat("en-GB", {
  timeZone: IST_TZ,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

const IST_DATE_FMT = new Intl.DateTimeFormat("en-IN", {
  timeZone: IST_TZ,
  day: "numeric",
  month: "short",
  year: "numeric",
});

const INR_FMT = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

function istParts(d: Date): Record<string, string> {
  return IST_DATETIME_FMT.formatToParts(d).reduce<Record<string, string>>((acc, p) => {
    acc[p.type] = p.value;
    return acc;
  }, {});
}

/** "2026-06-25 · 14:42:07 IST" — the live console clock. */
export function istClock(d: Date): string {
  const p = istParts(d);
  return `${p.year}-${p.month}-${p.day} · ${p.hour}:${p.minute}:${p.second} IST`;
}

/** "2026-06-25 14:42" in IST — compact stamps (no seconds, no label). */
export function istDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const p = istParts(d);
  return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}`;
}

/** "25 Jun 2026" in IST, Indian English. */
export function istDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return IST_DATE_FMT.format(d);
}

/** "₹25,00,000" — full rupee figure with Indian (2,3) digit grouping. */
export function inr(value: number): string {
  return INR_FMT.format(value);
}

/** "₹12.5L" — lakh shorthand for compensation (null → null). */
export function inrLakh(value: number | null): string | null {
  if (value === null) return null;
  return `₹${(value / 100_000).toFixed(value % 100_000 === 0 ? 0 : 1)}L`;
}
