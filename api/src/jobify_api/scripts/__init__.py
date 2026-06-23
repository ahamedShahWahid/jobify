"""One-shot developer scripts (seeding, maintenance, etc.).

Distinct from `jobify_worker` (long-running async tasks) and `jobify.routes`
(HTTP handlers). Each module here exposes a `main()` returning an
``int`` exit code and is invokable as ``python -m jobify.scripts.<name>``.
"""
