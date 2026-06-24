import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "../../api/client";
import type { EmployerRead, InviteRead, MemberRead } from "../../api/types";
import { EmptyState, ErrorNotice, Field, Stamp } from "../../components/bits";
import { useSession } from "../../session";

/**
 * Mirror the backend InviteCreate guard (length 3–254, '@' present and not at an
 * end) so a doomed invite is caught before the request instead of returning a
 * raw 422 — and so the gate matches what the server will accept.
 */
function isValidInviteEmail(v: string): boolean {
  return (
    v.length >= 3 && v.length <= 254 && v.includes("@") && !v.startsWith("@") && !v.endsWith("@")
  );
}

export function Team() {
  const { client, identity } = useSession();
  const [employers, setEmployers] = useState<EmployerRead[]>([]);
  const [employerId, setEmployerId] = useState<string | null>(null);
  const [members, setMembers] = useState<MemberRead[] | null>(null);
  const [invites, setInvites] = useState<InviteRead[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"owner" | "member">("member");
  const [inviteBusy, setInviteBusy] = useState(false);

  useEffect(() => {
    client.myEmployers().then(
      (list) => {
        setEmployers(list);
        setEmployerId((current) => current ?? list[0]?.id ?? null);
      },
      (e) => setError(errorMessage(e)),
    );
  }, [client]);

  const refresh = useCallback(async () => {
    if (!employerId) return;
    setError(null);
    try {
      const [memberList, inviteList] = await Promise.all([
        client.listMembers(employerId),
        client.listInvites(employerId),
      ]);
      setMembers(memberList);
      setInvites(inviteList);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [client, employerId]);

  useEffect(() => {
    setMembers(null);
    setInvites(null);
    void refresh();
  }, [refresh]);

  const myRow = members?.find((m) => m.user_id === identity.id);
  const iAmOwner = myRow?.role === "owner";
  const owners = (members ?? []).filter((m) => m.role === "owner");

  async function act(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function sendInvite() {
    if (!employerId) return;
    const email = inviteEmail.trim();
    if (!isValidInviteEmail(email)) {
      setError("Enter a valid email (3–254 characters, '@' not at the start or end).");
      return;
    }
    setInviteBusy(true);
    setError(null);
    try {
      await client.createInvite(employerId, email, inviteRole);
      setInviteEmail(""); // only clear on success — keep the input if it failed
      await refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setInviteBusy(false);
    }
  }

  return (
    <>
      <div className="headline rise">
        <h1>
          TEAM <span className="ghost">ROSTER</span>
        </h1>
        <div className="sub">
          <span className="flavor">Owners steer; members read. The last owner can never leave.</span>
        </div>
      </div>

      {employers.length > 1 && (
        <div className="filters rise" style={{ gridTemplateColumns: "minmax(220px, 380px)" }}>
          <label className="field">
            <span className="k">employer</span>
            <select value={employerId ?? ""} onChange={(e) => setEmployerId(e.target.value)}>
              {employers.map((employer) => (
                <option key={employer.id} value={employer.id}>
                  {employer.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      <ErrorNotice error={error} />

      {employers.length === 0 ? (
        <EmptyState>You're not part of any employer yet.</EmptyState>
      ) : (
        <>
          <div className="panel rise mb">
            <div className="panel-head">
              <span className="k">
                members{members ? ` · ${members.length}` : ""} ({owners.length} owner
                {owners.length === 1 ? "" : "s"})
              </span>
              {!iAmOwner && members && <span className="chip">read-only — you're a member</span>}
            </div>
            <div className="table-wrap" style={{ border: 0 }}>
              <table className="console">
                <thead>
                  <tr>
                    <th>Person</th>
                    <th>Role</th>
                    <th>Added</th>
                    <th className="r">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {(members ?? []).map((member) => {
                    const isSelf = member.user_id === identity.id;
                    const lastOwner = member.role === "owner" && owners.length <= 1;
                    return (
                      <tr key={member.user_id}>
                        <td>
                          {member.display_name ?? <span className="dim">—</span>}
                          {isSelf && (
                            <span className="chip acc" style={{ marginLeft: 8 }}>
                              you
                            </span>
                          )}
                          <div className="k" style={{ marginTop: 2 }}>
                            {member.email ?? "—"}
                          </div>
                        </td>
                        <td>
                          {member.role === "owner" ? (
                            <span className="chip acc">owner</span>
                          ) : (
                            <span className="chip">member</span>
                          )}
                        </td>
                        <td>
                          <Stamp iso={member.added_at} />
                        </td>
                        <td className="r" style={{ whiteSpace: "nowrap" }}>
                          {iAmOwner && !isSelf && (
                            <>
                              <button
                                className="btn ghost sm"
                                title={lastOwner ? "Cannot demote the last owner" : undefined}
                                disabled={lastOwner}
                                onClick={() =>
                                  void act(() =>
                                    client.changeMemberRole(
                                      employerId!,
                                      member.user_id,
                                      member.role === "owner" ? "member" : "owner",
                                    ),
                                  )
                                }
                              >
                                {member.role === "owner" ? "Demote" : "Make owner"}
                              </button>{" "}
                              <button
                                className="btn danger sm"
                                disabled={lastOwner}
                                onClick={() =>
                                  void act(() => client.removeMember(employerId!, member.user_id))
                                }
                              >
                                Remove
                              </button>
                            </>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {members !== null && members.length === 0 && (
                <EmptyState>Empty roster — that shouldn't happen.</EmptyState>
              )}
            </div>
          </div>

          <div className="panel rise">
            <div className="panel-head">
              <span className="k">invites</span>
            </div>
            {iAmOwner && (
              <div className="panel-body" style={{ borderBottom: "1px solid var(--line)" }}>
                <div className="field-row" style={{ gridTemplateColumns: "2fr 1fr auto" }}>
                  <Field label="Email">
                    <input
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                      placeholder="colleague@company.in"
                    />
                  </Field>
                  <Field label="Role">
                    <select
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value as "owner" | "member")}
                    >
                      <option value="member">member</option>
                      <option value="owner">owner</option>
                    </select>
                  </Field>
                  <div className="field" style={{ justifyContent: "flex-end" }}>
                    <span className="k">&nbsp;</span>
                    <button
                      className="btn primary"
                      disabled={inviteBusy || !isValidInviteEmail(inviteEmail.trim())}
                      onClick={() => void sendInvite()}
                    >
                      {inviteBusy ? "Sending…" : "Invite"}
                    </button>
                  </div>
                </div>
                <p className="hint" style={{ margin: 0, fontSize: 11, color: "var(--ink-faint)" }}>
                  Existing users get an in-app notification; new people find it under "My invites"
                  after their first sign-in. Invites expire after 7 days.
                </p>
              </div>
            )}
            <div className="table-wrap" style={{ border: 0 }}>
              <table className="console">
                <thead>
                  <tr>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Expires</th>
                    <th className="r">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {(invites ?? []).map((invite) => (
                    <tr key={invite.id}>
                      <td>{invite.email}</td>
                      <td>
                        <span className="chip">{invite.role}</span>
                      </td>
                      <td>
                        {invite.status === "pending" ? (
                          <span className="chip acc">
                            <span className="led amber" /> pending
                          </span>
                        ) : invite.status === "accepted" ? (
                          <span className="chip ok">accepted</span>
                        ) : (
                          <span className="chip">{invite.status}</span>
                        )}
                      </td>
                      <td>
                        <Stamp iso={invite.expires_at} />
                      </td>
                      <td className="r">
                        {iAmOwner && invite.status === "pending" && (
                          <button
                            className="btn danger sm"
                            onClick={() =>
                              void act(() => client.revokeInvite(employerId!, invite.id))
                            }
                          >
                            Revoke
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {invites !== null && invites.length === 0 && (
                <EmptyState>No invites yet.</EmptyState>
              )}
            </div>
          </div>
        </>
      )}
    </>
  );
}
