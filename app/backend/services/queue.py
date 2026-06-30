"""Tiny in-process job queue with N asyncio workers.

Each submitted coroutine becomes a Job; the queue tracks status, result, and
error. Suitable for the desktop app's needs; no Redis, no Celery.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    status: JobStatus
    result: Any = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status.value,
            "error": self.error,
        }


class JobQueue:
    def __init__(self, workers: int = 2):
        self.workers = workers
        self._jobs: dict[str, Job] = {}
        self._futures: dict[str, asyncio.Future] = {}
        self._q: asyncio.Queue = asyncio.Queue()
        self._tasks: list[asyncio.Task] = []
        self._started = False
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self) -> None:
        if self._started:
            return
        self._loop = asyncio.get_event_loop()
        for _ in range(self.workers):
            self._tasks.append(self._loop.create_task(self._worker()))
        self._started = True

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()
        self._started = False

    async def submit(self, func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Job:
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        job_id = f"job_{uuid.uuid4().hex[:10]}"
        job = Job(id=job_id, status=JobStatus.PENDING)
        self._jobs[job_id] = job
        self._futures[job_id] = future
        await self._q.put((job_id, func, args, kwargs, future))
        return job

    async def wait(self, job_id: str, timeout: float | None = None) -> Job:
        """Block until the job is in a terminal state or timeout elapses.

        Returns the Job. Raises asyncio.TimeoutError if the timeout is hit
        while the job is still running.
        """
        job = self._jobs[job_id]
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            return job
        deadline = None
        if timeout is not None:
            loop = asyncio.get_event_loop()
            deadline = loop.time() + timeout
        while True:
            future = self._futures.get(job_id)
            if future is not None and future.done():
                # Drain outcome silently.
                try:
                    future.result()
                except Exception:
                    pass
                return job
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                return job
            if deadline is not None and asyncio.get_event_loop().time() >= deadline:
                if future is not None and not future.done():
                    raise asyncio.TimeoutError
                return job
            await asyncio.sleep(0.01)

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    async def _worker(self) -> None:
        while True:
            job_id, func, args, kwargs, future = await self._q.get()
            job = self._jobs[job_id]
            job.status = JobStatus.RUNNING
            try:
                result = await func(*args, **kwargs)
                job.result = result
                job.status = JobStatus.COMPLETED
                if not future.done():
                    future.set_result(result)
            except Exception as exc:
                job.error = repr(exc)
                job.status = JobStatus.FAILED
                if not future.done():
                    future.set_exception(exc)
            finally:
                self._q.task_done()