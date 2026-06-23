import { useCallback, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../api/client";
import type { NotificationListResponse, NotificationRead } from "../api/types";
import { Masthead } from "../components/Chrome";
import { ago, EmptyState, ErrorNotice } from "../components/bits";
import { useSession } from "../session";
import { usePaged } from "./explore/usePaged";

/**
 * The Wire — the applicant's in-app notification desk. Real-backed: GET
 * /v1/notifications (pending/dispatching/sent only — failed is admin-only) and
 * POST /v1/notifications/{id}/read. Behind RequireApplicant.
 *
 * read_at drives the unread treatment. Rather than refetch on every open (which
 * would reset pagination), read state is tracked in a local overlay Set merged
 * at render — the API call fires in the background and is idempotent.
 */

type NotificationItem = { notification: NotificationRead };

function str(payload: Record<string, unknown>, key: string): string | null {
  const v = payload[key];
  return typeof v === "string" ? v : null;
}

interface Rendered {
  icon: string;
  kicker: string;
  title: ReactNode;
  body: ReactNode;
  href: string | null;
}

/** Map a notification's kind + payload to a human card. Unknown kinds degrade to
 *  a readable generic rather than throwing — the inbox must never break on a
 *  notification type the client predates. */
function render(n: NotificationRead): Rendered {
  if (n.kind === "application_received") {
    const job = str(n.payload, "job_title") ?? "a role";
    const employer = str(n.payload, "employer_name") ?? "the employer";
    const jobId = str(n.payload, "job_id");
    return {
      icon: "✦",
      kicker: "Application filed",
      title: (
        <>
          Your application reached <span className="nx-em">{employer}</span>
        </>
      ),
      body: (
        <>
          We sent your résumé for <span className="nx-strong">{job}</span>. You&apos;ll hear here if
          the recruiter moves it forward.
        </>
      ),
      href: jobId ? `/explore/jobs/${jobId}` : null,
    };
  }
  if (n.kind === "employer_invite") {
    const employer = str(n.payload, "employer_name") ?? "An employer";
    const role = str(n.payload, "role") ?? "member";
    return {
      icon: "✶",
      kicker: "Team invitation",
      title: (
        <>
          <span className="nx-em">{employer}</span> invited you to their hiring team
        </>
      ),
      body: (
        <>
          As <span className="nx-strong">{role}</span>. Accepting turns on your recruiter workspace.
        </>
      ),
      href: "/invites",
    };
  }
  // Unknown / future kind — show the raw kind, never crash.
  return {
    icon: "•",
    kicker: n.kind.replace(/_/g, " "),
    title: <>A new notification</>,
    body: <span className="dim">{JSON.stringify(n.payload)}</span>,
    href: null,
  };
}

export function Inbox() {
  const { client } = useSession();
  const fetcher = useCallback<(cursor: string | undefined) => Promise<NotificationListResponse>>(
    (cursor) => client.notifications(cursor),
    [client],
  );
  const { rows, nextCursor, busy, error, loadMore } = usePaged<NotificationItem>(fetcher, "inbox");

  // Local read overlay so marking-read doesn't refetch / reset pagination.
  const [readOverlay, setReadOverlay] = useState<Set<string>>(new Set());
  const [opError, setOpError] = useState<string | null>(null);

  const isRead = useCallback(
    (n: NotificationRead) => n.read_at !== null || readOverlay.has(n.id),
    [readOverlay],
  );

  const unreadCount = useMemo(
    () => rows.filter(({ notification }) => !isRead(notification)).length,
    [rows, isRead],
  );

  // Drop an id back out of the overlay — used to revert an optimistic read when
  // the server POST fails, so the UI never claims a read the server rejected.
  const revert = useCallback((id: string) => {
    setReadOverlay((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }, []);

  function markRead(n: NotificationRead) {
    if (isRead(n)) return;
    setReadOverlay((prev) => new Set(prev).add(n.id));
    client.markNotificationRead(n.id).catch((e) => {
      revert(n.id);
      setOpError(errorMessage(e));
    });
  }

  function markAllRead() {
    const unread = rows.map((r) => r.notification).filter((n) => !isRead(n));
    if (unread.length === 0) return;
    setReadOverlay((prev) => {
      const next = new Set(prev);
      unread.forEach((n) => next.add(n.id));
      return next;
    });
    unread.forEach((n) =>
      client.markNotificationRead(n.id).catch((e) => {
        revert(n.id);
        setOpError(errorMessage(e));
      }),
    );
  }

  return (
    <>
      <Masthead />
      <div className="wrap">
        <div style={{ padding: "26px 0 0" }}>
          <Link to="/explore" className="link-arrow" style={{ fontSize: 13 }}>
            ← Back to feed
          </Link>
        </div>

        <header className="nx-hero rise mt">
          <div>
            <span className="kicker">Dispatches</span>
            <h1 className="nx-h1">
              The Wire
              {unreadCount > 0 && (
                <span className="nx-badge num">
                  {unreadCount}
                  {nextCursor ? "+" : ""}
                </span>
              )}
            </h1>
            <p className="deck nx-deck">
              {unreadCount > 0
                ? `${unreadCount}${nextCursor ? "+" : ""} unread — application receipts and team invitations, in order.`
                : "Everything that's happened on your account, newest first."}
            </p>
          </div>
          {/* No bulk-read endpoint exists, so this marks the loaded rows. Labelled
              honestly when more pages remain. */}
          <button className="btn ghost sm" onClick={markAllRead} disabled={unreadCount === 0}>
            {nextCursor ? "Mark loaded read" : "Mark all read"}
          </button>
        </header>

        <ErrorNotice error={error ?? opError} />

        <section className="nx-list rise d1">
          {rows.map(({ notification }) => {
            const read = isRead(notification);
            const r = render(notification);
            const inner = (
              <>
                <div className={`nx-glyph${read ? "" : " unread"}`} aria-hidden="true">
                  {r.icon}
                </div>
                <div className="nx-body">
                  <div className="nx-line">
                    <span className="nx-kicker">{r.kicker}</span>
                    <span className="nx-meta num">
                      <span className={`nx-channel ${notification.channel}`}>
                        {notification.channel === "email" ? "email" : "in-app"}
                      </span>
                      <span className="nx-dot">·</span>
                      {ago(notification.created_at)}
                    </span>
                  </div>
                  <h3 className="nx-title">{r.title}</h3>
                  <p className="nx-text">{r.body}</p>
                  {r.href && (
                    <span className="nx-cta link-arrow">
                      Open <span className="arr">→</span>
                    </span>
                  )}
                </div>
                {!read && <span className="nx-unread-dot" aria-label="unread" />}
              </>
            );
            return r.href ? (
              <Link
                key={notification.id}
                to={r.href}
                className={`nx-row${read ? "" : " is-unread"}`}
                onClick={() => markRead(notification)}
              >
                {inner}
              </Link>
            ) : (
              <button
                key={notification.id}
                type="button"
                className={`nx-row${read ? "" : " is-unread"}`}
                onClick={() => markRead(notification)}
              >
                {inner}
              </button>
            );
          })}

          {rows.length === 0 && !busy && !error && (
            <EmptyState>
              Nothing on the wire yet. Apply to a role and your receipt lands here — along with any
              team invitations.
            </EmptyState>
          )}
        </section>

        {nextCursor && (
          <div className="nx-more">
            <button className="btn" disabled={busy} onClick={loadMore}>
              {busy ? "Loading…" : "Older dispatches"}
            </button>
          </div>
        )}

        <div className="cb-foot-rule" />
      </div>
    </>
  );
}
