# PR #61 Review Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve every actionable PR #61 review item with guarded outbox leases, bounded retention, stronger failure-path coverage, accurate client contracts, and verified GitHub thread closure.

**Architecture:** Extend the existing notification claim-token pattern to outbox events instead of introducing a generic queue framework. Keep operational additions bounded: one migration, one cleanup task, focused helpers for test seams, and pure frontend state derivation.

**Tech Stack:** Python 3.12, SQLAlchemy 2 async, Alembic, PostgreSQL 16, Celery 5, Redis 7 Lua, pytest, structlog, React 18, TypeScript 5.6, Vitest, Flutter/Dart, Riverpod code generation.

## Global Constraints

- Preserve at-least-once outbox delivery; external outbox consumers remain idempotent.
- Add `JOBIFY_OUTBOX_RETENTION_DAYS` with default 30 and bounds 1–3650.
- Add `JOBIFY_OUTBOX_CLEANUP_BATCH_SIZE` with default 1000 and bounds 1–10,000.
- Schedule `jobify.cleanup_outbox` every 86,400 seconds.
- Never log outbox payloads, task arguments, recipient addresses, or storage keys.
- Use `FOR UPDATE SKIP LOCKED` for both claims and cleanup.
- Do not change public HTTP API response shapes.
- Keep `flutter-app-state.png` untracked and out of every commit.

---

### Task 1: Persist Outbox Claim Ownership

**Files:**
- Create: `core/src/jobify/db/migrations/versions/0024_outbox_dispatch_token.py`
- Modify: `core/src/jobify/db/models.py`
- Modify: `tests/integration/test_migrations.py`

**Interfaces:**
- Produces: nullable `OutboxEvent.dispatch_token: UUID | None` mapped to `jobify.outbox_events.dispatch_token`.
- Consumes: Alembic head `0023` and the existing PostgreSQL UUID conventions.

- [ ] **Step 1: Write the failing migration test**

```python
@pytest.mark.integration
async def test_outbox_has_dispatch_token_column(session: AsyncSession) -> None:
    columns = await session.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'jobify' AND table_name = 'outbox_events'
    """))
    assert "dispatch_token" in {row[0] for row in columns}
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/integration/test_migrations.py::test_outbox_has_dispatch_token_column -v`

Expected: FAIL because `dispatch_token` is absent from the migrated schema.

- [ ] **Step 3: Add migration and model field**

```python
# core/src/jobify/db/migrations/versions/0024_outbox_dispatch_token.py
"""Add per-claim ownership tokens to outbox processing.

Revision ID: 0024
Revises: 0023
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024"
down_revision = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "outbox_events",
        sa.Column("dispatch_token", postgresql.UUID(as_uuid=True), nullable=True),
        schema="jobify",
    )


def downgrade() -> None:
    op.drop_column("outbox_events", "dispatch_token", schema="jobify")
```

Add to `OutboxEvent` beside `locked_until`:

```python
dispatch_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
```

- [ ] **Step 4: Verify GREEN and model/migration parity**

Run: `uv run pytest tests/integration/test_migrations.py::test_outbox_has_dispatch_token_column -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/src/jobify/db/models.py core/src/jobify/db/migrations/versions/0024_outbox_dispatch_token.py tests/integration/test_migrations.py
git commit -m "fix: add outbox claim ownership token"
```

### Task 2: Guard Outbox Claims, Completion, and Failure

**Files:**
- Modify: `worker/src/jobify_worker/tasks/sweep_outbox.py`
- Modify: `tests/integration/test_sweep_outbox.py`

**Interfaces:**
- Produces: `_claim(sm) -> list[tuple[UUID, UUID]]`.
- Produces: `_complete(sm, event_id, dispatch_token) -> None`.
- Changes: `_process_one(..., dispatch_token: UUID, ...) -> None` and `_record_failure(sm, event_id, dispatch_token, exc) -> None`.
- Consumes: `OutboxEvent.dispatch_token` from Task 1.

- [ ] **Step 1: Add failing null-lock and stale-token tests**

```python
@pytest.mark.asyncio
async def test_claim_reclaims_processing_event_with_null_lock(session: AsyncSession) -> None:
    event = OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        status=OutboxEventStatus.PROCESSING,
        locked_until=None,
        payload={"task_name": "jobify.parse_resume", "args": ["id"]},
    )
    session.add(event)
    await session.commit()
    claims = await _claim(_make_sm(session))
    await session.refresh(event)
    assert claims == [(event.id, event.dispatch_token)]
    assert event.dispatch_token is not None


@pytest.mark.asyncio
async def test_stale_token_cannot_complete_or_reschedule_reclaimed_event(
    session: AsyncSession,
) -> None:
    stale = uuid4()
    current = uuid4()
    event = OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        status=OutboxEventStatus.PROCESSING,
        dispatch_token=current,
        locked_until=datetime.now(UTC) + timedelta(minutes=1),
        attempts=2,
        payload={"task_name": "jobify.parse_resume", "args": ["id"]},
    )
    session.add(event)
    await session.commit()

    await _complete(_make_sm(session), event.id, stale)
    await _record_failure(_make_sm(session), event.id, stale, RuntimeError("late"))

    await session.refresh(event)
    assert event.status == OutboxEventStatus.PROCESSING
    assert event.dispatch_token == current
    assert event.last_error is None
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/integration/test_sweep_outbox.py -k 'null_lock or stale_token' -v`

Expected: FAIL because null locks are not claimable and token-aware helpers do not exist.

- [ ] **Step 3: Implement token-aware claims and state writes**

Use `uuid4()` for every claim, include `locked_until.is_(None)` in the processing reclaim predicate, and append `(event.id, token)`. Add these helpers:

```python
def _owns_claim(event: OutboxEvent, dispatch_token: UUID) -> bool:
    return (
        event.status == OutboxEventStatus.PROCESSING
        and event.dispatch_token == dispatch_token
    )


def _clear_claim(event: OutboxEvent) -> None:
    event.dispatch_token = None
    event.locked_until = None
```

Move the completion transaction into `_complete`; require `_owns_claim` before mutation. Pass the token through `_sweep_outbox_async`, `_process_one`, `_complete`, and `_record_failure`. Clear ownership on completed, pending, and failed transitions.

At claim exhaustion emit:

```python
_log.warning(
    "outbox.claim-exhausted",
    event_id=str(event.id),
    attempts=event.attempts,
)
```

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/integration/test_sweep_outbox.py -k 'null_lock or stale_token' -v`

Expected: both tests PASS.

- [ ] **Step 5: Add terminal-failure, backoff, batch-isolation, and logging tests**

Add the following assertions in focused async tests, using a freshly read non-null token after `_claim` whenever the event begins pending:

```python
# _record_failure terminal branch
event.attempts = settings.outbox_max_attempts
await _record_failure(sm, event.id, event.dispatch_token, RuntimeError("poison"))
assert event.status == OutboxEventStatus.FAILED
assert event.dispatch_token is None

# retry backoff
before = datetime.now(UTC)
await _record_failure(sm, event.id, event.dispatch_token, RuntimeError("broker"))
assert event.available_at > before

# batch isolation
def dispatch(name: str, args: list[object]) -> None:
    if args == ["poison"]:
        raise RuntimeError("poison")
poison = OutboxEvent(
    kind=OutboxEventKind.TASK_DISPATCH,
    payload={"task_name": "jobify.parse_resume", "args": ["poison"]},
)
healthy = OutboxEvent(
    kind=OutboxEventKind.TASK_DISPATCH,
    payload={"task_name": "jobify.parse_resume", "args": ["healthy"]},
)
session.add_all([poison, healthy])
await session.commit()
await _sweep_outbox_async(sm=sm, storage=FakeStorage(), dispatch=dispatch)
await session.refresh(poison)
await session.refresh(healthy)
assert poison.status == OutboxEventStatus.PENDING
assert healthy.status == OutboxEventStatus.COMPLETED

# claim-exhausted observability
with capture_logs() as logs:
    await _sweep_outbox_async(sm=sm, storage=FakeStorage(), dispatch=dispatch)
assert any(row["event"] == "outbox.claim-exhausted" for row in logs)
```

- [ ] **Step 6: Run these tests and verify expected failures before completing any missing behavior**

Run: `uv run pytest tests/integration/test_sweep_outbox.py -v`

Expected before final implementation: new assertions expose any unimplemented branch; after minimal fixes all tests PASS.

- [ ] **Step 7: Add a real two-connection claim test**

```python
@pytest.mark.integration
async def test_concurrent_claimers_claim_event_once(migrated_db: str) -> None:
    engine = create_async_engine(migrated_db, poolclass=NullPool)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    event_id: UUID | None = None
    try:
        async with sm() as seed_session:
            event = OutboxEvent(
                kind=OutboxEventKind.TASK_DISPATCH,
                payload={"task_name": "jobify.parse_resume", "args": ["concurrent"]},
            )
            seed_session.add(event)
            await seed_session.commit()
            event_id = event.id

        first, second = await asyncio.gather(_claim(sm), _claim(sm))
        claims = first + second
        assert len(claims) == 1
        assert claims[0][0] == event_id
    finally:
        if event_id is not None:
            async with sm() as cleanup_session:
                await cleanup_session.execute(
                    delete(OutboxEvent).where(OutboxEvent.id == event_id)
                )
                await cleanup_session.commit()
        await engine.dispose()
```

- [ ] **Step 8: Verify the full outbox integration file**

Run: `uv run pytest tests/integration/test_sweep_outbox.py -v`

Expected: PASS with no duplicate claim and no swallowed batch failure.

- [ ] **Step 9: Commit**

```bash
git add worker/src/jobify_worker/tasks/sweep_outbox.py tests/integration/test_sweep_outbox.py
git commit -m "fix: guard outbox state by claim token"
```

### Task 3: Add Bounded Terminal Outbox Cleanup

**Files:**
- Create: `worker/src/jobify_worker/tasks/cleanup_outbox.py`
- Create: `tests/integration/test_cleanup_outbox.py`
- Modify: `worker/src/jobify_worker/settings.py`
- Modify: `worker/src/jobify_worker/celery_app.py`
- Modify: `worker/src/jobify_worker/worker_app.py`
- Modify: `tests/unit/test_settings.py`
- Modify: `tests/unit/test_celery_app.py`
- Modify: `.env.example`
- Modify: `worker/README.md`

**Interfaces:**
- Produces: `_cleanup_outbox_async(*, sm=None, now=None) -> int` and Celery task `jobify.cleanup_outbox`.
- Consumes: terminal `OutboxEventStatus.COMPLETED` and `FAILED` rows.

- [ ] **Step 1: Write failing settings and schedule tests**

```python
def test_outbox_cleanup_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    settings = WorkerSettings()
    assert settings.outbox_retention_days == 30
    assert settings.outbox_cleanup_batch_size == 1000


def test_cleanup_outbox_is_beat_scheduled() -> None:
    entry = celery_app.conf.beat_schedule["cleanup-outbox"]
    assert entry["task"] == "jobify.cleanup_outbox"
    assert entry["schedule"].run_every.total_seconds() == 86400
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/test_settings.py tests/unit/test_celery_app.py -k 'outbox_cleanup or cleanup_outbox' -v`

Expected: FAIL because the settings and schedule are absent.

- [ ] **Step 3: Add validated settings and schedule**

```python
outbox_retention_days: int = Field(default=30, ge=1, le=3650)
outbox_cleanup_batch_size: int = Field(default=1000, ge=1, le=10_000)
```

Route `jobify.cleanup_outbox` to the `outbox` queue and schedule it with `celery_schedule(run_every=86400)`. Import `cleanup_outbox` from `worker_app.py`.

- [ ] **Step 4: Write the failing cleanup behavior test**

```python
@pytest.mark.integration
async def test_cleanup_deletes_only_expired_live_terminal_rows(
    session: AsyncSession,
) -> None:
    now = datetime(2026, 7, 18, tzinfo=UTC)
    old = now - timedelta(days=31)
    rows = [
        OutboxEvent(
            kind=OutboxEventKind.TASK_DISPATCH,
            status=OutboxEventStatus.COMPLETED,
            payload={},
            updated_at=old,
        ),
        OutboxEvent(
            kind=OutboxEventKind.TASK_DISPATCH,
            status=OutboxEventStatus.FAILED,
            payload={},
            updated_at=old,
        ),
        OutboxEvent(
            kind=OutboxEventKind.TASK_DISPATCH,
            status=OutboxEventStatus.COMPLETED,
            payload={},
            updated_at=now - timedelta(days=1),
        ),
        OutboxEvent(
            kind=OutboxEventKind.TASK_DISPATCH,
            status=OutboxEventStatus.PENDING,
            payload={"task_name": "jobify.parse_resume", "args": ["pending"]},
            updated_at=old,
        ),
        OutboxEvent(
            kind=OutboxEventKind.TASK_DISPATCH,
            status=OutboxEventStatus.COMPLETED,
            payload={},
            updated_at=old,
            deleted_at=now - timedelta(days=2),
        ),
    ]
    session.add_all(rows)
    await session.commit()
    deleted_ids = {rows[0].id, rows[1].id}

    assert await _cleanup_outbox_async(sm=_make_sm(session), now=now) == 2
    remaining = set(
        (await session.execute(select(OutboxEvent.id).where(
            OutboxEvent.id.in_([row.id for row in rows])
        ))).scalars()
    )
    assert deleted_ids.isdisjoint(remaining)
    assert len(remaining) == 3


@pytest.mark.integration
async def test_cleanup_respects_batch_limit(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 7, 18, tzinfo=UTC)
    session.add_all([
        OutboxEvent(
            kind=OutboxEventKind.TASK_DISPATCH,
            status=OutboxEventStatus.COMPLETED,
            payload={},
            updated_at=now - timedelta(days=31),
        )
        for _ in range(2)
    ])
    await session.commit()
    monkeypatch.setattr(settings, "outbox_cleanup_batch_size", 1)
    assert await _cleanup_outbox_async(sm=_make_sm(session), now=now) == 1
```

- [ ] **Step 5: Verify RED**

Run: `uv run pytest tests/integration/test_cleanup_outbox.py -v`

Expected: FAIL because `cleanup_outbox.py` does not exist.

- [ ] **Step 6: Implement bounded cleanup**

```python
stmt = (
    select(OutboxEvent)
    .where(
        OutboxEvent.deleted_at.is_(None),
        OutboxEvent.status.in_((OutboxEventStatus.COMPLETED, OutboxEventStatus.FAILED)),
        OutboxEvent.updated_at < cutoff,
    )
    .order_by(OutboxEvent.updated_at, OutboxEvent.id)
    .limit(settings.outbox_cleanup_batch_size)
    .with_for_update(skip_locked=True)
)
rows = (await session.execute(stmt)).scalars().all()
for event in rows:
    await session.delete(event)
await session.commit()
```

Log `outbox.cleanup-completed` with `deleted_count`, `retention_days`, and `cutoff`, but no event payload data.

- [ ] **Step 7: Document settings and verify**

Add both exact environment variables and defaults to `.env.example` and `worker/README.md`.

Run: `uv run pytest tests/unit/test_settings.py tests/unit/test_celery_app.py tests/integration/test_cleanup_outbox.py -v`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add .env.example worker/README.md worker/src/jobify_worker/settings.py worker/src/jobify_worker/celery_app.py worker/src/jobify_worker/worker_app.py worker/src/jobify_worker/tasks/cleanup_outbox.py tests/unit/test_settings.py tests/unit/test_celery_app.py tests/integration/test_cleanup_outbox.py
git commit -m "feat: prune terminal outbox events"
```

### Task 4: Cover Notification Claim and Failure Edges

**Files:**
- Modify: `worker/src/jobify_worker/tasks/sweep_notifications.py`
- Modify: `tests/integration/test_sweep_notifications.py`

**Interfaces:**
- Consumes: existing `_claim_notifications`, `_dispatch_one`, `_owns_claim`, and `_clear_claim` functions.
- Produces: structured `sweep.claim-exhausted` warning at terminal claim recovery.

- [ ] **Step 1: Add failing tests for claim loss after send, consent revocation, missing recipient, and terminal logging**

Add these exact arrangements and assertions (with `UserConsent`, `ConsentScope`, `uuid4`, and `capture_logs` imports):

```python
@pytest.mark.integration
async def test_sweep_does_not_complete_stale_claim_after_dispatch(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session, email="stale@example.com")
    notification = await _seed_notification(session, user)
    await session.commit()
    sm = _make_sm(session)

    class _TokenStealingChannel:
        async def send(
            self, row: Notification, *, recipient: str
        ) -> ChannelResult:
            async with sm() as claim_session:
                current = await claim_session.get(Notification, row.id, with_for_update=True)
                assert current is not None
                current.dispatch_token = uuid4()
                current.locked_until = datetime.now(UTC) + timedelta(minutes=1)
                await claim_session.commit()
            return ChannelResult.success()

    await _sweep_notifications_async(
        sm=sm,
        email_channel=_TokenStealingChannel(),
        batch_size=10,
    )
    await session.refresh(notification)
    assert notification.status == NotificationStatus.DISPATCHING
    assert notification.sent_at is None


@pytest.mark.integration
async def test_sweep_cancels_when_transactional_email_consent_is_revoked(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session, email="revoked@example.com")
    notification = await _seed_notification(session, user)
    session.add(UserConsent(
        user_id=user.id,
        scope=ConsentScope.EMAIL_TRANSACTIONAL.value,
        granted=False,
    ))
    await session.commit()
    await _sweep_notifications_async(sm=_make_sm(session), batch_size=10)
    await session.refresh(notification)
    assert notification.status == NotificationStatus.CANCELLED
    assert notification.last_error == "consent_revoked:email_transactional"


@pytest.mark.integration
async def test_sweep_fails_when_recipient_email_is_missing(session: AsyncSession) -> None:
    user = User(email=None, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    notification = await _seed_notification(session, user)
    await session.commit()
    await _sweep_notifications_async(sm=_make_sm(session), batch_size=10)
    await session.refresh(notification)
    assert notification.status == NotificationStatus.FAILED
    assert notification.last_error == "user_missing_or_no_email"


@pytest.mark.integration
async def test_sweep_logs_claim_exhaustion(session: AsyncSession) -> None:
    user = await _seed_user(session, email="exhausted@example.com")
    notification = await _seed_notification(
        session,
        user,
        status=NotificationStatus.DISPATCHING,
        attempts=_worker_settings.notify_max_attempts,
    )
    notification.dispatch_token = uuid4()
    notification.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()
    with capture_logs() as logs:
        await _sweep_notifications_async(sm=_make_sm(session), batch_size=10)
    assert any(row["event"] == "sweep.claim-exhausted" for row in logs)
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/integration/test_sweep_notifications.py -k 'claim_lost_after_dispatch or revoked or missing_email or claim_exhausted' -v`

Expected: behavioral edge tests reveal missing fixtures/assertions; the logging test fails because no warning is emitted.

- [ ] **Step 3: Add the terminal warning; preserve the already-correct guarded state transitions**

```python
_log.warning(
    "sweep.claim-exhausted",
    notification_id=str(notification.id),
    attempts=notification.attempts,
)
```

Do not log the recipient email or notification payload.

- [ ] **Step 4: Verify GREEN and commit**

Run: `uv run pytest tests/integration/test_sweep_notifications.py -v`

Expected: PASS.

```bash
git add worker/src/jobify_worker/tasks/sweep_notifications.py tests/integration/test_sweep_notifications.py
git commit -m "test: cover notification dispatch recovery"
```

### Task 5: Execute Real Redis Lua and Assert Exact Queue Metrics

**Files:**
- Create: `tests/integration/test_rate_limit.py`
- Modify: `tests/integration/test_operational_metrics.py`

**Interfaces:**
- Consumes: `RedisRateLimiter`, `JOBIFY_REDIS_URL`, and `/metrics`.
- Produces: integration evidence that Redis executes `_SCRIPT` atomically and metrics report exact database counts.

- [ ] **Step 1: Write the real Redis Lua boundary test**

```python
@pytest.mark.integration
async def test_rate_limit_lua_allows_limit_and_rejects_next() -> None:
    client = redis.asyncio.Redis.from_url(os.environ["JOBIFY_REDIS_URL"])
    prefix = f"test:rate:{uuid4()}"
    limiter = RedisRateLimiter(client, prefix=prefix)
    try:
        assert await limiter.hit(key="boundary", limit=2, window_seconds=60) == 1
        assert await limiter.hit(key="boundary", limit=2, window_seconds=60) == 0
        with pytest.raises(RateLimitExceededError) as raised:
            await limiter.hit(key="boundary", limit=2, window_seconds=60)
        assert 1 <= raised.value.retry_after <= 60
    finally:
        await client.delete(f"{prefix}:boundary")
        await client.aclose()
```

- [ ] **Step 2: Run the Redis test**

Run: `uv run pytest tests/integration/test_rate_limit.py -v`

Expected: PASS against Redis 7 locally/CI; unlike the unit fake, this executes the Lua script.

- [ ] **Step 3: Strengthen the metrics test with seeded exact counts**

Seed two pending notifications, one failed notification, one processing outbox event, and one completed outbox event through the shared `session`:

```python
user = User(email="metrics@example.com", role=UserRole.APPLICANT)
session.add(user)
await session.flush()
session.add_all([
    Notification(
        user_id=user.id,
        kind="application_received",
        channel=NotificationChannel.IN_APP,
        status=NotificationStatus.PENDING,
        payload={},
    ),
    Notification(
        user_id=user.id,
        kind="application_received",
        channel=NotificationChannel.IN_APP,
        status=NotificationStatus.PENDING,
        payload={},
    ),
    Notification(
        user_id=user.id,
        kind="application_received",
        channel=NotificationChannel.IN_APP,
        status=NotificationStatus.FAILED,
        payload={},
    ),
    OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        status=OutboxEventStatus.PROCESSING,
        payload={"task_name": "jobify.parse_resume", "args": ["metrics"]},
    ),
    OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        status=OutboxEventStatus.COMPLETED,
        payload={},
    ),
])
await session.commit()
response = await async_client.get("/metrics")
body = response.text
assert 'jobify_async_items{queue="notifications",status="pending"} 2' in body
assert 'jobify_async_items{queue="notifications",status="failed"} 1' in body
assert 'jobify_async_items{queue="outbox",status="processing"} 1' in body
assert 'jobify_async_items{queue="outbox",status="completed"} 1' in body
```

Parse both age gauge values as floats and assert they are non-negative.

- [ ] **Step 4: Verify and commit**

Run: `uv run pytest tests/integration/test_rate_limit.py tests/integration/test_operational_metrics.py -v`

Expected: PASS.

```bash
git add tests/integration/test_rate_limit.py tests/integration/test_operational_metrics.py
git commit -m "test: execute rate-limit Lua and pin metrics"
```

### Task 6: Make Outbox Requeue Recovery Testable

**Files:**
- Modify: `worker/src/jobify_worker/scripts/requeue_outbox.py`
- Create: `tests/integration/test_requeue_outbox.py`

**Interfaces:**
- Produces: `_requeue_rows(sm, *, limit: int, dry_run: bool) -> int`.
- Changes: `_requeue` constructs/disposes the engine and delegates to `_requeue_rows`.

- [ ] **Step 1: Write failing dry-run and live requeue tests**

```python
@pytest.mark.integration
async def test_requeue_dry_run_does_not_mutate_failed_event(session: AsyncSession) -> None:
    token = uuid4()
    failed = OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        status=OutboxEventStatus.FAILED,
        attempts=10,
        last_error="broker down",
        locked_until=datetime.now(UTC) - timedelta(minutes=1),
        dispatch_token=token,
        payload={"task_name": "jobify.parse_resume", "args": ["failed"]},
    )
    session.add(failed)
    await session.commit()
    assert await _requeue_rows(_make_sm(session), limit=100, dry_run=True) == 1
    await session.refresh(failed)
    assert failed.status == OutboxEventStatus.FAILED
    assert failed.dispatch_token == token
    assert failed.attempts == 10


@pytest.mark.integration
async def test_requeue_resets_failed_event_only(session: AsyncSession) -> None:
    failed = OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        status=OutboxEventStatus.FAILED,
        attempts=10,
        last_error="broker down",
        locked_until=datetime.now(UTC) - timedelta(minutes=1),
        dispatch_token=uuid4(),
        payload={"task_name": "jobify.parse_resume", "args": ["failed"]},
    )
    completed = OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        status=OutboxEventStatus.COMPLETED,
        payload={},
    )
    session.add_all([failed, completed])
    await session.commit()
    before = datetime.now(UTC)
    assert await _requeue_rows(_make_sm(session), limit=100, dry_run=False) == 1
    await session.refresh(failed)
    await session.refresh(completed)
    assert failed.status == OutboxEventStatus.PENDING
    assert failed.attempts == 0
    assert failed.last_error is None
    assert failed.locked_until is None
    assert failed.dispatch_token is None
    assert failed.available_at >= before
    assert completed.status == OutboxEventStatus.COMPLETED
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/integration/test_requeue_outbox.py -v`

Expected: FAIL because `_requeue_rows` is absent.

- [ ] **Step 3: Extract the sessionmaker helper and clear claim ownership**

```python
async def _requeue_rows(
    sm: async_sessionmaker[AsyncSession], *, limit: int, dry_run: bool
) -> int:
    async with sm() as session:
        rows = (
            (
                await session.execute(
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.status == OutboxEventStatus.FAILED,
                        OutboxEvent.deleted_at.is_(None),
                    )
                    .order_by(OutboxEvent.created_at, OutboxEvent.id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        if dry_run:
            await session.rollback()
            return len(rows)
        for event in rows:
            event.status = OutboxEventStatus.PENDING
            event.available_at = datetime.now(UTC)
            event.dispatch_token = None
            event.locked_until = None
            event.attempts = 0
            event.last_error = None
        await session.commit()
        return len(rows)
```

- [ ] **Step 4: Verify and commit**

Run: `uv run pytest tests/integration/test_requeue_outbox.py -v`

Expected: PASS.

```bash
git add worker/src/jobify_worker/scripts/requeue_outbox.py tests/integration/test_requeue_outbox.py
git commit -m "test: cover outbox recovery requeue"
```

### Task 7: Tighten Console Contracts and Analytics Failure State

**Files:**
- Modify: `frontend/scripts/check-api-contract.mjs`
- Create: `frontend/src/sites/console/pages/admin/analyticsState.ts`
- Create: `frontend/src/sites/console/pages/admin/analyticsState.test.ts`
- Modify: `frontend/src/sites/console/pages/admin/Analytics.tsx`

**Interfaces:**
- Produces: `analyticsRequestState(summary, error) -> "loading" | "ready" | "error"`.
- Consumes: OpenAPI schemas `AuditAnalyticsRead`, `AdminEmployerRead`, `CountBucketRead`, and `DayBucketRead`.

- [ ] **Step 1: Expand the contract gate**

Add these exact schema fields:

```javascript
AuditAnalyticsRead: [
  "action_counts", "activity", "distinct_actors", "last_24h", "role_counts",
  "span_end", "span_start", "system_events", "total_events",
],
AdminEmployerRead: [
  "created_at", "gst", "id", "name", "reason", "reviewed_at", "status",
],
CountBucketRead: ["count", "key"],
DayBucketRead: ["count", "day"],
```

Rename `recruiterContract` to `clientContract` and update the success message to `OpenAPI contract matches the React clients.`

- [ ] **Step 2: Run the contract check**

Run: `npm run check:contract`

Expected: PASS and report the updated general client-contract message.

- [ ] **Step 3: Write the failing analytics state test**

```typescript
import { describe, expect, it } from "vitest";
import { analyticsRequestState } from "./analyticsState";

describe("analyticsRequestState", () => {
  it("stops loading when the initial request fails", () => {
    expect(analyticsRequestState(null, "unavailable")).toBe("error");
  });

  it("distinguishes loading and ready data", () => {
    expect(analyticsRequestState(null, null)).toBe("loading");
    expect(analyticsRequestState({} as never, null)).toBe("ready");
  });
});
```

- [ ] **Step 4: Verify RED**

Run: `npm test -- analyticsState.test.ts`

Expected: FAIL because `analyticsState.ts` is absent.

- [ ] **Step 5: Implement the pure state helper and use it**

```typescript
import type { AdminAnalyticsSummary } from "../../api/types";

export function analyticsRequestState(
  summary: AdminAnalyticsSummary | null,
  error: string | null,
): "loading" | "ready" | "error" {
  if (summary !== null) return "ready";
  if (error !== null) return "error";
  return "loading";
}
```

In `Analytics.tsx`, derive `const requestState = analyticsRequestState(summary, error)` and `const loading = requestState === "loading"`. Keep the existing `ErrorNotice`; the derived state prevents loading placeholders on failure.

- [ ] **Step 6: Verify and commit**

Run: `npm test -- analyticsState.test.ts`

Run: `npm run build`

Expected: Vitest and production build PASS.

```bash
git add frontend/scripts/check-api-contract.mjs frontend/src/sites/console/pages/admin/Analytics.tsx frontend/src/sites/console/pages/admin/analyticsState.ts frontend/src/sites/console/pages/admin/analyticsState.test.ts
git commit -m "fix: tighten console contract and error state"
```

### Task 8: Correct Flutter Contract Naming and Regenerate Outputs

**Files:**
- Modify: `app/test/unit/data/jobs/recruiter_openapi_contract_test.dart`
- Conditionally modify: generated `app/lib/**/*.g.dart` files only when build_runner changes them.

**Interfaces:**
- Produces: accurately named backend snapshot pin; no runtime API changes.

- [ ] **Step 1: Rename the test description**

```dart
test('backend recruiter schemas pin the expected wire fields', () {
```

- [ ] **Step 2: Run the focused test**

Run: `flutter test test/unit/data/jobs/recruiter_openapi_contract_test.dart`

Expected: PASS.

- [ ] **Step 3: Regenerate and inspect output**

Run: `dart run build_runner build --delete-conflicting-outputs`

Run: `git status --short app/lib app/test/unit/data/jobs/recruiter_openapi_contract_test.dart`

Expected: source hashes are normalized; commit generated files only if they actually differ.

- [ ] **Step 4: Format and commit**

Run: `dart format --output=none --set-exit-if-changed lib test`

```bash
git add app/test/unit/data/jobs/recruiter_openapi_contract_test.dart app/lib
git commit -m "test: clarify Flutter contract coverage"
```

### Task 9: Full Verification, Push, and GitHub Thread Completion

**Files:**
- Modify only if verification exposes a regression in a file already covered by Tasks 1–8.

**Interfaces:**
- Consumes: all prior task commits.
- Produces: pushed branch, inline replies, resolved threads, and a top-level review-summary response.

- [ ] **Step 1: Run Python quality gates**

Run: `uv run ruff check core/src api/src worker/src tests`

Run: `uv run ruff format --check core/src api/src worker/src tests`

Run: `uv run mypy`

Run: `uv run pytest -v -m "not integration and not eval"`

Run: `uv run pytest -v -m integration`

Run: `uv run pytest -v -s -m eval`

Expected: all commands exit zero.

- [ ] **Step 2: Run frontend gates**

Run from `frontend`: `npm test`

Run from `frontend`: `npm run build`

Expected: all tests, contract validation, TypeScript compilation, and Vite build pass.

- [ ] **Step 3: Run Flutter gates**

Run from `app`: `dart run build_runner build --delete-conflicting-outputs`

Run from `app`: `dart format --output=none --set-exit-if-changed lib test`

Run from `app`: `flutter analyze`

Run from `app`: `flutter test`

Expected: no generated drift, no formatting changes, no analyzer findings, and all tests pass.

- [ ] **Step 4: Audit the final diff**

Run: `git diff --check`

Run: `git status --short`

Run: `git diff origin/main...HEAD --stat`

Expected: no unresolved or whitespace errors; `flutter-app-state.png` remains the only unrelated untracked file.

- [ ] **Step 5: Push**

Run: `git push origin applicant-feed-home`

Expected: GitHub remote advances to the final local commit.

- [ ] **Step 6: Reply to each inline review comment**

Resolve `FINAL_SHA` once, then reply with the concrete fix associated with each comment:

```bash
FINAL_SHA="$(git rev-parse --short HEAD)"
gh api repos/ahamedShahWahid/jobify/pulls/61/comments/3607557150/replies -f body="Fixed in ${FINAL_SHA}: PROCESSING rows with null locks are reclaimable. Verified by the outbox integration suite."
gh api repos/ahamedShahWahid/jobify/pulls/61/comments/3607557160/replies -f body="Fixed in ${FINAL_SHA}: terminal claim exhaustion now emits outbox.claim-exhausted with bounded structured fields. Verified by the outbox logging test."
gh api repos/ahamedShahWahid/jobify/pulls/61/comments/3607557166/replies -f body="Fixed in ${FINAL_SHA}: outbox completion and failure writes now require the exact per-claim dispatch token. Verified by stale-token and concurrent-claim tests."
gh api repos/ahamedShahWahid/jobify/pulls/61/comments/3607557171/replies -f body="Fixed in ${FINAL_SHA}: notification terminal claim exhaustion now emits sweep.claim-exhausted. Verified by the notification integration suite."
gh api repos/ahamedShahWahid/jobify/pulls/61/comments/3607557176/replies -f body="Fixed in ${FINAL_SHA}: the React contract gate now pins AuditAnalyticsRead, AdminEmployerRead, CountBucketRead, and DayBucketRead. Verified by npm run build."
gh api repos/ahamedShahWahid/jobify/pulls/61/comments/3607557182/replies -f body="Fixed in ${FINAL_SHA}: analytics request state stops rendering loading placeholders after an initial error. Verified by analyticsState.test.ts and npm run build."
gh api repos/ahamedShahWahid/jobify/pulls/61/comments/3607557186/replies -f body="Fixed in ${FINAL_SHA}: the Flutter test name now accurately states that it pins backend recruiter schema wire fields. Verified by the focused Flutter test and build_runner."
```

- [ ] **Step 7: Resolve inline threads and summarize non-inline review items**

Fetch thread node IDs through GraphQL:

```bash
gh api graphql -f query='query { repository(owner:"ahamedShahWahid", name:"jobify") { pullRequest(number:61) { reviewThreads(first:100) { nodes { id isResolved comments(first:1) { nodes { databaseId } } } } } } }'
```

For each unresolved returned node whose `databaseId` is one of the seven addressed comment IDs, execute this mutation with that exact node ID:

```bash
gh api graphql -f query='mutation($id:ID!) { resolveReviewThread(input:{threadId:$id}) { thread { id isResolved } } }' -F id=THREAD_NODE_ID
```

Then post the non-inline summary:

```bash
gh pr comment 61 --body "Addressed the full review summary: added bounded terminal outbox cleanup; real two-connection claim coverage; Redis 7 Lua boundary execution; exact operational-metric counts; notification stale-claim, consent, and missing-recipient coverage; recovery requeue coverage; and fresh Dart generation verification. Full Python, frontend, and Flutter gates are recorded in the pushed commit."
```

- [ ] **Step 8: Verify PR state**

Run: `gh pr view 61 --json url,state,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup`

Expected: PR remains open, has no unresolved addressed threads, and GitHub reports the current merge/check state without `DIRTY` conflicts.
