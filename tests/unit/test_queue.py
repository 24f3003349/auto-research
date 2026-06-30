"""Tests for the background job queue."""
import asyncio

import pytest

from app.backend.services.queue import JobQueue, JobStatus, Job


@pytest.mark.asyncio
async def test_queue_runs_job_and_records_status():
    q = JobQueue(workers=1)
    q.start()

    async def task(x, y):
        await asyncio.sleep(0.01)
        return x + y

    job = await q.submit(task, 1, y=2)
    final = await q.wait(job.id, timeout=2.0)
    assert final.status == JobStatus.COMPLETED
    assert final.result == 3


@pytest.mark.asyncio
async def test_queue_records_failure_status():
    q = JobQueue(workers=1)
    q.start()

    async def task():
        raise RuntimeError("boom")

    job = await q.submit(task)
    final = await q.wait(job.id, timeout=2.0)
    assert final.status == JobStatus.FAILED
    assert "boom" in (final.error or "")


@pytest.mark.asyncio
async def test_queue_processes_in_parallel_with_multiple_workers():
    q = JobQueue(workers=2)
    q.start()

    results: list[int] = []

    async def slow(i):
        await asyncio.sleep(0.05)
        results.append(i)
        return i

    jobs = [await q.submit(slow, i) for i in range(4)]
    for j in jobs:
        await q.wait(j.id, timeout=2.0)
    assert sorted(results) == [0, 1, 2, 3]


@pytest.mark.asyncio
async def test_queue_wait_raises_timeout_when_job_stuck():
    q = JobQueue(workers=1)
    q.start()

    async def task():
        await asyncio.sleep(2.0)
        return 1

    job = await q.submit(task)
    with pytest.raises(asyncio.TimeoutError):
        await q.wait(job.id, timeout=0.05)