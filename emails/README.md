# Jobify — Email Templates

Production-grade HTML email templates for the Jobify **notifications outbox**.

> "Warm editorial broadsheet" — bone paper, warm ink, persimmon accent, forest-green
> "verified". Same brand language as the applicant web surface (`frontend/src/sites/web/styles/site.css`).

These are **real transactional emails**. Today the outbox's email channel is the
`LoggingEmailChannel` stub (it logs `email.sent`); real SES is deferred. When a real
`EmailChannel` ships, these templates are the markup it renders — so they're a genuine
deliverable, not a mock.

## No build step

Pure static HTML/CSS. No framework, no bundler, no preprocessing. Every template is a
complete standalone `.html` document that renders correctly when opened directly in a
browser **and** in email clients (table-based layout, inlined critical styles, a `<style>`
block only for `@media` mobile / dark-mode enhancements and the optional Fraunces import).

## Templates (`templates/`)

| File | Kind | Channel | Status | Recipient |
|------|------|---------|--------|-----------|
| `application_received.html` | `application_received` | email | **Wired today** | Applicant — confirms their application was filed |
| `employer_invite.html` | `employer_invite` | email | **Wired today** | Invitee — invitation to join an employer team |
| `match_surfaced.html` | `match_surfaced` | email | **Proposed** | Applicant — digest of newly-surfaced matches (the signature email) |
| `dsr_export_ready.html` | `dsr_export_ready` | email | **Proposed** | Data subject — "your data export is ready" (DPDP) |

**Wired today** = the notifications outbox already emits this notification kind (the
`application_received` row on apply; the `employer_invite` row when an invited email maps
to an existing user). The email *body* below is what a real `EmailChannel` would render.

**Proposed** = no email path emits this yet; designed forward-looking.
- `match_surfaced` — the scoring worker sets `matches.surfaced_at`, but nothing is
  outboxed on surface. This digest is the product's signature email.
- `dsr_export_ready` — DSR export is synchronous HTTP today (`POST /v1/me/dsr/export`
  returns the JSON envelope inline). This email is for an async-export future.

Each template's top-of-file HTML comment documents its `kind`, `channel`, WIRED/PROPOSED
status, and the exact `payload` fields it consumes. Inline example values are paired with
`<!-- {{field}} -->` comments so the payload → content mapping is obvious.

## Real values come from the outbox

The example values baked into each file (so it previews standalone) stand in for the real
values, which come from each notification's **`payload` dict** in the `notifications`
table. A real `EmailChannel` substitutes `{{job_title}}`, `{{employer_name}}`, etc. from
`notification.payload` at send time.

## Preview

Open the studio gallery — a vanilla-JS preview page that renders all four templates in
iframes with **light/dark** and **desktop (600px) / mobile (360px)** toggles plus each
template's metadata (kind, channel, status badge, payload fields):

```bash
open emails/index.html
```

Or serve the directory (better for iframe reloads / avoiding `file://` quirks):

```bash
npx serve emails
# then visit the printed localhost URL
```

You can also open any individual template directly:

```bash
open emails/templates/match_surfaced.html
```

## Craft notes

- **Table-based layout**, 600px centered content, full-bleed background wrapper. No
  flexbox/grid for structure.
- **Inline styles** carry the critical styling; the `<head>` `<style>` block holds only
  `@media (max-width:600px)` (mobile stacking) and `@media (prefers-color-scheme: dark)`.
- **Bulletproof buttons** — padding-based `<a>` in a bordered table cell, with VML
  fallback for Outlook (`mso` conditional comments).
- **Dark mode** inverts paper/ink while keeping the persimmon accent legible.
- **Accessible** — real `<a>` text, semantic heading hierarchy, a hidden preheader span,
  no external images (a text wordmark "Jobify." avoids image-blocking).
- **Fraunces** display serif is progressive enhancement (`@import` + `<link>`); it
  degrades to a Georgia/serif stack since web fonts are unreliable in email. Body uses a
  Hanken Grotesk → system sans stack; scores use a JetBrains Mono → ui-monospace stack.
