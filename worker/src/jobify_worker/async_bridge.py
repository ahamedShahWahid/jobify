"""One sync-Celery to async-body bridge shared by every task."""

from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


def run_async(coro_factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """Run an async task body, including from eager tests with an active loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro_factory()).result()
    return asyncio.run(coro_factory())
