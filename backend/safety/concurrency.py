import asyncio
from collections.abc import Coroutine
from typing import Any


async def run_both[A, B](
    first: Coroutine[Any, Any, A], second: Coroutine[Any, Any, B]
) -> tuple[A, B]:
    """Run two calls concurrently. If either fails, cancel the other and raise its error."""
    try:
        async with asyncio.TaskGroup() as group:
            a = group.create_task(first)
            b = group.create_task(second)
    except ExceptionGroup as group_error:
        raise group_error.exceptions[0] from None
    return a.result(), b.result()
