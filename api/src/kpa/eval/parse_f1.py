"""F1 scoring for the LibraryResumeParser against the gold dataset.

Scores four fields per example:
- ``name`` (scalar)
- ``email`` (scalar, lowercased)
- ``phone`` (scalar, digits-only)
- ``skills`` (set)

Per-example contributions accumulate into per-field (TP, FP, FN) totals.
Per-field F1 = 2*TP / (2*TP + FP + FN). Overall F1 is the unweighted
arithmetic mean of the four per-field F1s — macro-averaging so a field
with only a handful of relevant items doesn't get drowned out by skills.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

from kpa.integrations.parser.base import ParsedResume
from kpa.integrations.parser.library import (
    _extract_email,
    _extract_name,
    _extract_phone,
    _extract_skills,
)


class _ExpectedExample(TypedDict, total=False):
    name: str | None
    email: str | None
    phone: str | None
    skills: list[str]

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "parse_eval"


def _normalize_name(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.casefold().split())


def _normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().casefold()


def _normalize_phone(value: str | None) -> str | None:
    if value is None:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits or None


def _normalize_skill_set(values: list[str]) -> set[str]:
    return {v.strip().casefold() for v in values if v.strip()}


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def add(self, other: Counts) -> None:
        self.tp += other.tp
        self.fp += other.fp
        self.fn += other.fn

    def f1(self) -> float:
        denom = 2 * self.tp + self.fp + self.fn
        if denom == 0:
            return 1.0
        return (2 * self.tp) / denom


def _score_scalar(predicted: str | None, expected: str | None) -> Counts:
    if predicted is None and expected is None:
        return Counts()
    if predicted is None and expected is not None:
        return Counts(fn=1)
    if predicted is not None and expected is None:
        return Counts(fp=1)
    if predicted == expected:
        return Counts(tp=1)
    # Both non-null but mismatch — counts as both a missed expectation
    # AND a wrong prediction.
    return Counts(fp=1, fn=1)


def _score_set(predicted: set[str], expected: set[str]) -> Counts:
    return Counts(
        tp=len(predicted & expected),
        fp=len(predicted - expected),
        fn=len(expected - predicted),
    )


@dataclass
class ExampleResult:
    example_id: str
    per_field: dict[str, Counts]
    parsed_name: str | None
    parsed_email: str | None
    parsed_phone: str | None
    parsed_skills: list[str]
    expected_name: str | None
    expected_email: str | None
    expected_phone: str | None
    expected_skills: list[str]

    def overall_f1(self) -> float:
        return sum(c.f1() for c in self.per_field.values()) / len(self.per_field)


@dataclass
class EvalReport:
    examples: list[ExampleResult]
    per_field_totals: dict[str, Counts] = field(default_factory=dict)

    @property
    def per_field_f1(self) -> dict[str, float]:
        return {name: c.f1() for name, c in self.per_field_totals.items()}

    @property
    def overall_f1(self) -> float:
        f1s = list(self.per_field_f1.values())
        return sum(f1s) / len(f1s) if f1s else 0.0

    def summary(self) -> str:
        lines = ["Parse F1 eval — gold dataset:"]
        for name, f1 in self.per_field_f1.items():
            c = self.per_field_totals[name]
            lines.append(f"  {name:<8} F1={f1:.3f}  (TP={c.tp}, FP={c.fp}, FN={c.fn})")
        lines.append(f"  {'overall':<8} F1={self.overall_f1:.3f}")
        return "\n".join(lines)

    def example_breakdown(self) -> str:
        lines = ["Per-example F1:"]
        for ex in self.examples:
            lines.append(f"  {ex.example_id}  F1={ex.overall_f1():.3f}")
            for fname, c in ex.per_field.items():
                lines.append(
                    f"    {fname:<8} F1={c.f1():.3f}  TP={c.tp} FP={c.fp} FN={c.fn}"
                )
        return "\n".join(lines)


def _parse_text_only(text: str) -> ParsedResume:
    """Run the parser's extraction heuristics directly on a text string.

    Bypasses ``LibraryResumeParser.parse`` (which invokes ``extract_text``
    on bytes). The F1 gate is testing extraction quality, not the
    byte->text step.
    """
    return ParsedResume(
        parser_name="library.v1.eval",
        raw_text=text,
        name=_extract_name(text),
        email=_extract_email(text),
        phone=_extract_phone(text),
        skills=_extract_skills(text),
    )


def _load_examples(data_dir: Path) -> list[tuple[str, str, _ExpectedExample]]:
    """Return list of (example_id, raw_text, expected_dict).

    Pairs each ``<id>.txt`` with the matching ``<id>.expected.json``. Skips
    the README and any orphan files.
    """
    examples: list[tuple[str, str, _ExpectedExample]] = []
    for txt_path in sorted(data_dir.glob("*.txt")):
        expected_path = txt_path.with_suffix(".expected.json")
        if not expected_path.exists():
            continue
        raw_text = txt_path.read_text(encoding="utf-8")
        expected: _ExpectedExample = json.loads(expected_path.read_text(encoding="utf-8"))
        examples.append((txt_path.stem, raw_text, expected))
    return examples


def eval_gold_dataset(data_dir: Path | None = None) -> EvalReport:
    """Score the LibraryResumeParser against the gold dataset and return
    the per-field + overall F1 report."""
    data_dir = data_dir or DEFAULT_DATA_DIR
    examples = _load_examples(data_dir)
    if not examples:
        raise RuntimeError(f"no gold examples found in {data_dir}")

    per_field_totals: dict[str, Counts] = {
        "name": Counts(),
        "email": Counts(),
        "phone": Counts(),
        "skills": Counts(),
    }
    results: list[ExampleResult] = []
    for example_id, text, expected in examples:
        parsed = _parse_text_only(text)
        per_field: dict[str, Counts] = {}

        per_field["name"] = _score_scalar(
            _normalize_name(parsed.name),
            _normalize_name(expected.get("name")),
        )
        per_field["email"] = _score_scalar(
            _normalize_email(parsed.email),
            _normalize_email(expected.get("email")),
        )
        per_field["phone"] = _score_scalar(
            _normalize_phone(parsed.phone),
            _normalize_phone(expected.get("phone")),
        )
        per_field["skills"] = _score_set(
            _normalize_skill_set(parsed.skills),
            _normalize_skill_set(expected.get("skills", [])),
        )

        for k, counts in per_field.items():
            per_field_totals[k].add(counts)

        results.append(
            ExampleResult(
                example_id=example_id,
                per_field=per_field,
                parsed_name=parsed.name,
                parsed_email=parsed.email,
                parsed_phone=parsed.phone,
                parsed_skills=list(parsed.skills),
                expected_name=expected.get("name"),
                expected_email=expected.get("email"),
                expected_phone=expected.get("phone"),
                expected_skills=list(expected.get("skills", [])),
            )
        )

    return EvalReport(examples=results, per_field_totals=per_field_totals)
