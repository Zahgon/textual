from __future__ import annotations

from asyncio import Lock, Task, current_task


class RLock:
    """A re-entrant asyncio lock."""

    def __init__(self) -> None:
        self._owner: Task | None = None
        self._count = 0
        self._lock = Lock()

    async def acquire(self) -> None:
        """Wait until the lock can be acquired."""
        pass

    def release(self) -> None:
        """Release a previously acquired lock."""
        pass

    @property
    def is_locked(self):
        """Return True if lock is acquired."""
        pass

    async def __aenter__(self) -> None:
        """Asynchronous context manager to acquire and release lock."""
        await self.acquire()

    async def __aexit__(self, _type, _value, _traceback) -> None:
        """Exit the context manager."""
        self.release()


if __name__ == "__main__":
    from asyncio import Lock

    async def locks():
        lock = RLock()
        async with lock:
            async with lock:
                print("Hello")

    import asyncio

    asyncio.run(locks())
