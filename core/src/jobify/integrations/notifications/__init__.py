"""Notification channel adapters for the Jobify outbox pattern.

This package provides a Protocol-based abstraction (``EmailChannel``) and
concrete implementations. For the MVP, ``LoggingEmailChannel`` is the only
impl — it logs the would-be email payload via structlog instead of sending.
A future ``SESEmailChannel`` will drop in without changing caller code.

Selected via ``JOBIFY_EMAIL_CHANNEL`` env var: ``logging`` (default) or ``ses``.
"""
