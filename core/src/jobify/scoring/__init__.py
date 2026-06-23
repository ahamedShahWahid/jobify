"""Pure-function scoring: vector cosine + structured rule fits + composition.

Three modules:
- ``vector`` — cosine similarity.
- ``structured`` — per-rule fits and their aggregate.
- ``match`` — composition into a single weighted score with threshold flag.

Stateless, no DB, no Celery. Used by ``score_applicant`` and ``score_job`` workers.
"""
