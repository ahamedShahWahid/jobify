# Parse F1 gold dataset

Eight hand-crafted synthetic resumes covering realistic patterns for the
Indian placement-market context Jobify targets. Each example is two files:

- `<id>-<name-slug>.txt` — raw resume text (UTF-8, no extraction needed).
- `<id>-<name-slug>.expected.json` — expected `name`, `email`, `phone`, and
  `skills` values per the `ParsedResume` schema.

## Why text-only

The F1 gate measures the **parser's extraction quality** — not the text
extractor (pdfplumber / python-docx). Feeding raw text directly bypasses
the byte → text step so a regression in `extract_text` doesn't bleed into
the F1 numbers. Text-extraction reliability is its own gate that lives
elsewhere when needed.

## Why only four fields

`name`, `email`, `phone`, `skills` are the highest-signal fields and the
ones the regex/keyword parser handles deterministically. `experience`,
`education`, and `certifications` are extracted by noisier heuristics
(date-range scanning, degree-keyword + nearby-year). They get F1 reports
in the eval output for visibility but **do not gate CI** in v0.

When the LLM parser ships, all seven fields will gate.

## How to score

- **Scalar fields** (`name`, `email`, `phone`): one example per case.
  Normalization:
  - `name`: case-fold + trim.
  - `email`: lowercase + trim.
  - `phone`: digits-only.

  TP = predicted matches expected. FP = predicted non-null but expected
  null (or mismatch when both non-null). FN = expected non-null but
  predicted null (or mismatch when both non-null). A mismatch counts as
  both FP and FN.

- **`skills`**: set intersection. Predicted and expected normalized via
  case-fold. TP = |predicted ∩ expected|; FP = |predicted - expected|;
  FN = |expected - predicted|.

- **Per-example F1** = `2·TP / (2·TP + FP + FN)`.

- **Per-field F1** = macro-average across examples (sum TP/FP/FN across
  examples, then F1).

- **Overall F1** = macro-average across the four gated fields.

## CI gate (v0)

- Overall F1 ≥ 0.85 (spec §13 P1 target).
- Per-field floor: `email` ≥ 0.95, `phone` ≥ 0.85, `name` ≥ 0.70,
  `skills` ≥ 0.75.

Below either gate fails the test. Ratchet upward as the parser improves —
spec target is ≥ 0.90 before launch.

## Adding examples

1. Drop a `.txt` + `.expected.json` pair with the next ID.
2. Re-run `uv run pytest -m eval -v`. Inspect the per-example breakdown.
3. If the new example tanks a field's F1 below floor, decide: is the
   expectation wrong, or is the parser legitimately weak? Adjust either
   the floor (and document why) or the expectation.
