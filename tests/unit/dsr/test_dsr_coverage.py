"""Guard test (P2.5b) — DSR PII-table coverage symmetry.

Pure reflection over the two DSR modules' namespaces; no DB, no app boot.

Why this exists (see memory "New PII table -> DSR coverage"): a new table
holding user PII must be wired into BOTH the DSR export builder
(`jobify_api.dsr.build_user_export`) and the DSR delete orchestrator
(`jobify_api.dsr.deleter.delete_user_data`). Adding it to one but not the
other — or to neither — is a DPDP gap that design review keeps missing.

Observable chosen: the set of ORM mapped classes each module *references*
(imported into its namespace). The modules don't expose a clean enumerable
of "covered tables", and re-parsing source is brittle; but every model a
module imports is genuinely used (ruff F401 forbids unused imports, enforced
in CI), so the imported-model set is a reliable, non-source-parsing proxy
for "tables this module touches". We then assert each module's referenced
PII tables equal an EXPLICIT expected set, after subtracting the documented
intentional asymmetries below.

Failure modes this catches:
  * add a new PII table to BOTH modules but forget to pin it here -> both
    equality assertions fail until EXPECTED_PII_TABLES is updated;
  * add a PII table to ONE module only -> the asymmetric module's set no
    longer equals EXPECTED -> fails, naming the table;
  * remove a PII table from either module -> fails, naming the table.
"""

from __future__ import annotations

import jobify_api.dsr as export_mod
import jobify_api.dsr.deleter as deleter_mod
from jobify.db.models import Base

# Tables holding user PII that MUST appear in BOTH the export and the
# deleter. Adding a new PII table to db/models.py requires adding it HERE
# AND wiring it into export (jobify_api/dsr/__init__.py) AND the deleter
# (jobify_api/dsr/deleter.py). `employers`/`employer_users` are org-membership
# context rather than direct user PII, but both DSR modules reference them
# (export nests employer info; deleter scrubs memberships + warns on ownerless
# employers) so they stay part of the symmetric contract.
EXPECTED_PII_TABLES: frozenset[str] = frozenset(
    {
        "users",
        "applicants",
        "applicant_preferences",
        "resumes",
        "applicant_embeddings",
        "oauth_identities",
        "employer_invites",
        "employer_users",
        "employers",
        "notifications",
        "saved_jobs",
        "user_consents",
        "match_feedback",
    }
)

# Documented intentional asymmetries.
#   EXPORT-ONLY: anonymized aggregates / append-only history that are
#   deliberately KEPT on delete (so they never appear in the deleter), but
#   are returned in the right-of-access export. `audit_logs` survives via
#   actor_user_id ON DELETE SET NULL; applications/matches are anonymized
#   aggregates kept after the applicant is tombstoned; jobs belong to the
#   employer, not the user.
_EXPORT_ONLY_TABLES: frozenset[str] = frozenset({"applications", "matches", "audit_logs", "jobs"})
#   DELETE-ONLY: session secrets — hard-deleted on erasure, and deliberately
#   REDACTED from the export (see _REDACTIONS / _REDACTED_COLUMN_NAMES), so
#   they appear in the deleter but never in the export.
_DELETE_ONLY_TABLES: frozenset[str] = frozenset({"refresh_tokens"})


def _referenced_tablenames(module: object) -> frozenset[str]:
    """Tablenames of every ORM mapped class imported into ``module``'s
    namespace. Imports are use-implying because CI's ruff run forbids unused
    imports (F401)."""
    names: set[str] = set()
    for obj in vars(module).values():
        if (
            isinstance(obj, type)
            and obj is not Base
            and issubclass(obj, Base)
            and hasattr(obj, "__tablename__")
        ):
            names.add(obj.__tablename__)
    return frozenset(names)


def test_export_covers_exactly_the_expected_pii_tables() -> None:
    export_tables = _referenced_tablenames(export_mod)
    covered_pii = export_tables - _EXPORT_ONLY_TABLES
    assert covered_pii == EXPECTED_PII_TABLES, (
        "DSR export PII coverage drifted from the pinned contract. "
        f"missing from export={EXPECTED_PII_TABLES - covered_pii}, "
        f"unpinned/new in export={covered_pii - EXPECTED_PII_TABLES}. "
        "Update EXPECTED_PII_TABLES (and confirm the deleter covers it too) "
        "or classify the table as an intentional asymmetry."
    )


def test_deleter_covers_exactly_the_expected_pii_tables() -> None:
    deleter_tables = _referenced_tablenames(deleter_mod)
    covered_pii = deleter_tables - _DELETE_ONLY_TABLES
    assert covered_pii == EXPECTED_PII_TABLES, (
        "DSR deleter PII coverage drifted from the pinned contract. "
        f"missing from deleter={EXPECTED_PII_TABLES - covered_pii}, "
        f"unpinned/new in deleter={covered_pii - EXPECTED_PII_TABLES}. "
        "Update EXPECTED_PII_TABLES (and confirm the export covers it too) "
        "or classify the table as an intentional asymmetry."
    )


def test_no_table_is_both_an_export_only_and_delete_only_exception() -> None:
    """The two asymmetry allowlists must be disjoint and must not overlap the
    PII set — a guard against a typo that would hide a real gap."""
    assert _EXPORT_ONLY_TABLES.isdisjoint(_DELETE_ONLY_TABLES)
    assert EXPECTED_PII_TABLES.isdisjoint(_EXPORT_ONLY_TABLES)
    assert EXPECTED_PII_TABLES.isdisjoint(_DELETE_ONLY_TABLES)
