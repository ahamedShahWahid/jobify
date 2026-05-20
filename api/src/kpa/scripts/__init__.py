"""One-shot developer scripts (seeding, maintenance, etc.).

Distinct from `kpa.workers` (long-running async tasks) and `kpa.routes`
(HTTP handlers). Each module here exposes a `main()` returning an
``int`` exit code and is invokable as ``python -m kpa.scripts.<name>``.
"""
