"""Resume-parser quality eval (spec §13 P1 gate).

The gate's wire is intentionally tiny:

    from kpa.eval.parse_f1 import eval_gold_dataset
    report = await eval_gold_dataset()
    assert report.overall_f1 >= 0.85

CI calls ``pytest -m eval`` which runs the test in ``tests/eval/`` and
fails if the gate slips. See ``api/data/parse_eval/000_README.md`` for the
gold-dataset format and threshold rationale.
"""
