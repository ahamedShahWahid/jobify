# Archive

Spent design/implementation artifacts — kept for provenance, not part of the active doc set and not maintained.

## `plans/`

Per-slice **implementation plans** from the brainstorm → spec → plan → subagent-driven-development workflow. Each was the step-by-step build script for one slice; once that slice merged, the plan is spent. The durable record lives elsewhere:

- **Why / contracts / reserved slugs** → the paired design doc in [`docs/superpowers/specs/`](../superpowers/specs/).
- **What shipped + load-bearing invariants** → the code, plus the per-section notes in [`CLAUDE.md`](../../CLAUDE.md).

These files may reference paths or APIs that have since changed. They remain in git history regardless; this directory just keeps them out of the active tree.
