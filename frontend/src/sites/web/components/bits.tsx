import type { ReactNode } from "react";
import type { JobRead } from "../api/types";
import { inrLakh } from "../../../shared/format";
import {
  EmptyState as SharedEmptyState,
  ErrorNotice as SharedErrorNotice,
} from "../../../shared/components/notices";

/** ₹ lakh formatting for CTC bands — delegates to the shared `inrLakh`. */
export function ctcBand(min: number | null, max: number | null): string {
  if (min === null && max === null) return "Undisclosed";
  return [min, max]
    .map(inrLakh)
    .filter((v): v is string => v !== null)
    .join(" – ");
}

/** Relative "Nd ago" from an ISO timestamp. */
export function ago(iso: string): string {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
  if (mins < 60) return `${Math.max(1, mins)}m ago`;
  if (mins < 60 * 36) return `${Math.round(mins / 60)}h ago`;
  return `${Math.round(mins / 1440)}d ago`;
}

export function VerifiedTag({ verified }: { verified: boolean }) {
  return verified ? (
    <span className="tag verified">✓ Verified</span>
  ) : (
    <span className="tag">Unverified</span>
  );
}

/** A 0.xx match score rendered as oversized editorial numerals. */
export function ScoreStamp({ score }: { score: number }) {
  return (
    <div className="score-stamp">
      <div className="v num">{score.toFixed(2)}</div>
      <div className="l">match</div>
    </div>
  );
}

export function JobFacts({ job }: { job: JobRead }) {
  return (
    <>
      <div className="factline">
        <span className="k">Compensation</span>
        <span className="v num">{ctcBand(job.ctc_min, job.ctc_max)}</span>
      </div>
      <div className="factline">
        <span className="k">Experience</span>
        <span className="v num">
          {job.min_exp_years}–{job.max_exp_years} yrs
        </span>
      </div>
      <div className="factline">
        <span className="k">Location</span>
        <span className="v">{job.locations.join(" · ")}</span>
      </div>
    </>
  );
}

export function ErrorNotice({ error }: { error: string | null }) {
  return <SharedErrorNotice error={error} className="notice err" />;
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <SharedEmptyState as="p" innerClassName="serif">
      {children}
    </SharedEmptyState>
  );
}
