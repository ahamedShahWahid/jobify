"""Guard test — no inline `users.role` writes outside membership.py.

Pure AST scan over source; no DB, no app boot.

Why this exists (arch review 2026-07, finding: api/src/jobify_api/routes/employers/core.py
re-implemented the exact APPLICANT->RECRUITER UPDATE inline instead of calling
flip_to_recruiter()). api/CLAUDE.md already tells a war story about the same
failure shape for `require_applicant` (inline-copied seven times, one copy
silently losing a filter) -- a code comment alone didn't prevent the role-flip
UPDATE from being re-inlined once already, so this test is the mechanical
backstop the DSR-coverage test already models for a different invariant
(tests/unit/dsr/test_dsr_coverage.py).

Scope: ONLY `update(User)....values(role=...)` -- a bulk role-mutation
statement. Deliberately does NOT flag:
  * `User(..., role=...)` at signup (auth/service.py) -- initial creation,
    not a flip, always APPLICANT.
  * `user.role = ...` direct attribute assignment (scripts/grant_admin.py) --
    a documented, separate, human-run admin path.
  * `update(User).values(...)` calls that never touch `role` (dsr/deleter.py's
    PII-scrub tombstone, routes/admin/users.py's suspend/unsuspend) -- real,
    legitimate User UPDATEs that aren't role writers.

Failure modes this catches:
  * a new join/leave/admin path re-inlines `update(User)...values(role=...)`
    instead of calling `flip_to_recruiter`/`maybe_demote_to_applicant` ->
    fails, naming the offending file.
"""

from __future__ import annotations

import ast
from pathlib import Path

_API_SRC = Path(__file__).resolve().parents[2] / "api" / "src" / "jobify_api"
_ALLOWED_FILE = _API_SRC / "employers" / "membership.py"


def _role_writing_update_calls(tree: ast.AST) -> list[ast.Call]:
    """Every `.values(...)` call, anywhere in `tree`, that (a) sets a `role`
    keyword and (b) is chained off an `update(User)` call."""
    hits: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Attribute) and node.func.attr == "values"):
            continue
        if not any(kw.arg == "role" for kw in node.keywords):
            continue
        if _chains_off_update_user(node.func.value):
            hits.append(node)
    return hits


def _chains_off_update_user(node: ast.AST) -> bool:
    """True if `node` is (or is built on top of) a call to `update(User)`."""
    for sub in ast.walk(node):
        if (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Name)
            and sub.func.id == "update"
            and any(isinstance(a, ast.Name) and a.id == "User" for a in sub.args)
        ):
            return True
    return False


def test_no_inline_role_writes_outside_membership() -> None:
    offenders: list[str] = []
    for path in _API_SRC.rglob("*.py"):
        if path == _ALLOWED_FILE:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        if _role_writing_update_calls(tree):
            offenders.append(str(path.relative_to(_API_SRC.parent.parent)))

    assert not offenders, (
        "Found inline `update(User)....values(role=...)` outside "
        "jobify_api/employers/membership.py in: "
        f"{offenders}. Role is derived from membership, never set directly "
        "(api/CLAUDE.md) -- call flip_to_recruiter()/maybe_demote_to_applicant() "
        "instead of re-implementing the flip."
    )


def test_membership_module_actually_has_the_role_writers() -> None:
    """Sanity check the allowlisted file isn't accidentally empty/renamed --
    else the guard above would trivially pass with zero real coverage."""
    tree = ast.parse(_ALLOWED_FILE.read_text(), filename=str(_ALLOWED_FILE))
    assert _role_writing_update_calls(tree), (
        f"{_ALLOWED_FILE} no longer contains a role-writing update(User) "
        "call -- has flip_to_recruiter been moved or rewritten? Update this "
        "test's _ALLOWED_FILE to match."
    )
