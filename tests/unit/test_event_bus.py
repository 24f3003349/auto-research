"""Tests for the in-process event bus."""
import asyncio

import pytest

from app.backend.services.event_bus import EventBus


@pytest.mark.asyncio
async def test_event_bus_broadcasts_to_subscribers():
    bus = EventBus()
    received: list[dict] = []
    async def handler(event):
        received.append(event)
    bus.subscribe(handler)
    await bus.publish({"type": "x", "value": 1})
    await asyncio.sleep(0)
    assert received == [{"type": "x", "value": 1}]


@pytest.mark.asyncio
async def test_event_bus_supports_multiple_subscribers():
    bus = EventBus()
    a, b = [], []
    bus.subscribe(lambda e: a.append(e))
    bus.subscribe(lambda e: b.append(e))
    await bus.publish({"type": "x"})
    assert a and b


@pytest.mark.asyncio
async def test_event_bus_unsubscribe_stops_delivery():
    bus = EventBus()
    received: list[dict] = []
    sub = bus.subscribe(lambda e: received.append(e))
    bus.unsubscribe(sub)
    await bus.publish({"type": "x"})
    assert received == []


@pytest.mark.asyncio
async def test_event_bus_continues_when_handler_raises():
    bus = EventBus()
    received: list[dict] = []
    def bad(_e):
        raise RuntimeError("boom")
    bus.subscribe(bad)
    bus.subscribe(lambda e: received.append(e))
    await bus.publish({"type": "x"})
    assert received == [{"type": "x"}]


@pytest.mark.asyncio
async def test_event_bus_history_is_bounded():
    bus = EventBus(max_history=3)
    for i in range(7):
        await bus.publish({"type": "tick", "i": i})
    hist = bus.history()
    assert len(hist) == 3
    assert [e["i"] for e in hist] == [4, 5, 6]  # rolling window