from __future__ import annotations

import importlib


def test_upgrade_quarantines_legacy_dispatches_without_requeueing(monkeypatch) -> None:
    migration = importlib.import_module(
        "jobify.db.migrations.versions.0023_notification_dispatch_leases"
    )
    executed: list[object] = []
    monkeypatch.setattr(migration.op, "add_column", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration.op, "execute", executed.append)

    migration.upgrade()

    transition = str(executed[0]).lower()
    assert "status = 'pending'" not in transition
    assert "status = 'dispatching'" in transition
    assert "locked_until" in transition
    assert "quarantine_seconds" in transition
    assert executed[0].compile().params == {"quarantine_seconds": 7500}
    assert str(executed[1]).startswith("CREATE INDEX")
