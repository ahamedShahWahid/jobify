"""Base types for notification channel adapters.

``EmailChannel`` is a structural Protocol — any class with a matching
``send`` signature satisfies it without inheriting. This keeps the adapters
decoupled from the base module and makes ``google.genai`` / ``boto3`` imports
lazy (the impl modules are never imported unless the specific channel is
selected).

``ChannelResult`` is the unified return value from every adapter call.
Adapters MUST return a ``ChannelResult`` for expected failures (network
blip, 4xx from the provider) and MUST only raise on programming errors or
fatal configuration issues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from jobify.db.models import Notification


class ChannelError(Exception):
    """Recoverable error from a channel adapter.

    Raise this (instead of returning ``ChannelResult.failed``) when the error
    is exceptional enough that the sweeper should treat it as a transient
    fault, increment ``attempts``, and reschedule. In practice, adapters
    should prefer returning ``ChannelResult.failed(message)`` so the sweeper
    can make a clean state transition without re-raising.
    """


@dataclass(frozen=True)
class ChannelResult:
    """Outcome of a single channel delivery attempt.

    Adapters return this; they never raise on expected delivery failures.

    Attributes:
        ok: True if the notification was delivered successfully.
        message: Human-readable detail for failed deliveries. Empty on success.
    """

    ok: bool
    message: str = field(default="")

    @classmethod
    def success(cls) -> ChannelResult:
        """Return a successful delivery result."""
        return cls(ok=True)

    @classmethod
    def failed(cls, message: str) -> ChannelResult:
        """Return a failed delivery result with an explanatory message."""
        return cls(ok=False, message=message)


class EmailChannel(Protocol):
    """Structural Protocol for email channel adapters.

    Implementations must be safe to call concurrently (the sweeper may
    dispatch multiple notifications in parallel in future). They must never
    raise on expected delivery failures; use ``ChannelResult.failed`` instead.

    Args:
        notification: The ``Notification`` ORM row being dispatched.
        recipient: The recipient email address (resolved by the sweeper from
            ``users.email``; not taken from the payload to avoid stale data).

    Returns:
        A ``ChannelResult`` indicating success or failure.
    """

    async def send(
        self,
        notification: Notification,
        *,
        recipient: str,
    ) -> ChannelResult: ...
