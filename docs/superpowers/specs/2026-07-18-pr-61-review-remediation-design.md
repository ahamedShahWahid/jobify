# PR #61 Review Remediation Design

## Goal

Address every actionable item in PR #61's inline review threads and review summary while preserving the existing durable-work architecture and avoiding unrelated refactors.

## Scope

The remediation covers four bounded areas:

1. Strengthen outbox lease ownership, recovery, observability, retention, and tests.
2. Close notification, rate-limiter, operational-metrics, and recovery-tool coverage gaps.
3. Tighten the console's API-contract and analytics error-state behavior.
4. Correct the Flutter contract-test name and regenerate source output to verify generated hashes.

The work does not redesign the queue abstraction, change external API behavior, or alter the already-merged applicant Feed feature.

## Outbox Lease Ownership

Migration `0024` adds a nullable UUID `dispatch_token` column to `jobify.outbox_events`. The SQLAlchemy model exposes the same field.

Each claim generates a new UUID and returns `(event_id, dispatch_token)`. Processing rows are claimable when their lease has expired or `locked_until` is null, matching notification recovery behavior. Completion and failure transitions require both `status = processing` and the exact token. A stale worker therefore cannot complete or reset a row reclaimed by another worker.

Claim ownership is cleared whenever an event leaves `processing`. Terminal events encountered at claim time emit a structured warning containing the event ID and attempt count. Notification claim exhaustion receives the symmetric warning.

The outbox retains at-least-once delivery semantics: external task/storage operations must remain idempotent because a process can still terminate after the external side effect and before its guarded completion commit.

## Terminal-Row Retention

A scheduled Celery task deletes terminal `completed` and `failed` outbox rows older than a configurable retention period. `JOBIFY_OUTBOX_RETENTION_DAYS` defaults to 30 and is bounded to 1–3650 days. `JOBIFY_OUTBOX_CLEANUP_BATCH_SIZE` defaults to 1000 and is bounded to 1–10,000 rows. Both settings are documented in `.env.example` and the worker README.

Cleanup uses `FOR UPDATE SKIP LOCKED` so it does not block sweepers or concurrent cleanup workers. Celery Beat runs `jobify.cleanup_outbox` every 86,400 seconds. The task logs only aggregate counts and cutoff metadata; it does not log payloads or storage keys.

Failed rows remain available for operator requeue during the retention window. Completed payloads continue to be cleared immediately after successful processing.

## Test Strategy

All behavioral changes follow red-green-refactor cycles.

Outbox integration coverage will verify:

- migration/model parity for `dispatch_token`;
- reclaiming `processing` rows with null locks;
- stale claim tokens cannot complete or reschedule a reclaimed event;
- `_record_failure` reaches terminal `failed` state at the attempt limit;
- exponential backoff advances `available_at`;
- one poison event does not prevent later batch rows from completing;
- two database connections cannot claim the same row concurrently;
- claim-exhaustion warnings are emitted;
- retention deletes only terminal rows older than the cutoff and respects the batch limit;
- dry-run and live operator requeue behavior reset the intended fields, including claim ownership.

Notification integration coverage will verify:

- a stale token detected after channel delivery cannot mutate the current claim;
- consent revocation transitions to `cancelled`;
- a missing recipient transitions to `failed`;
- claim exhaustion emits a warning.

Rate-limiter coverage will execute the Lua script through a Redis-compatible test implementation rather than returning canned `eval` results. It will pin first-hit expiry, `current == limit` allowance, and `current > limit` rejection with TTL-derived retry timing. If the selected fake Redis implementation requires a test-only Lua dependency, it will be added to the development dependency group and lockfile.

Operational-metrics integration coverage will seed known notification and outbox statuses, then assert exact emitted gauge values rather than label presence alone. The actionable-age gauges will be checked against bounded non-negative values.

The `SKIP LOCKED` contention test will use separate connections from the migrated integration database rather than the savepoint-bound single-connection fixture. Test cleanup will explicitly remove its seeded rows.

## Frontend Contract and Error State

The frontend contract gate will add the four admin schemas used by the modified console pages: `AuditAnalyticsRead`, `AdminEmployerRead`, `CountBucketRead`, and `DayBucketRead`. Expected fields will match the OpenAPI snapshot and TypeScript client types.

Analytics loading will be represented explicitly so a failed initial request renders the error notice without loading placeholders. A small pure state helper will be tested with Vitest to cover loading, ready, and failed states without adding a component-testing dependency solely for this fix.

## Flutter Contract Test

The recruiter OpenAPI test will be renamed to state what it actually verifies: the backend recruiter schema snapshot is pinned to the expected wire fields. Dart generation will be rerun with conflict deletion enabled. Generated files will be committed only when the generator changes them.

## GitHub Review Completion

After affected and full verification passes, the implementation will be committed and pushed to `applicant-feed-home`. Each inline comment will receive a thread reply describing the concrete fix and verification. Threads will be resolved only after the pushed commit contains the change. Review-summary items without inline threads will be summarized in one top-level PR response, including any item closed by evidence rather than a code change.

## Verification Gates

- Ruff and strict mypy for Python sources.
- Targeted unit and integration tests for every review item.
- Full Python unit and integration suites.
- Frontend contract check, Vitest suite, TypeScript build, and Vite production build.
- Flutter code generation, formatting, static analysis, and full test suite.
- Migration upgrade-to-head verification.
- Git diff checks for unresolved markers, whitespace errors, and accidental inclusion of `flutter-app-state.png`.
