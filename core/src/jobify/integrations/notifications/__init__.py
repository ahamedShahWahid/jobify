"""Notification channel adapters for the Jobify outbox pattern.

This package provides a Protocol-based abstraction (``EmailChannel``) and
concrete implementations. ``LoggingEmailChannel`` logs local deliveries;
``SesEmailChannel`` sends production transactional email through AWS SES.

Selected via ``JOBIFY_EMAIL_CHANNEL`` env var: ``logging`` (default) or ``ses``.
"""
