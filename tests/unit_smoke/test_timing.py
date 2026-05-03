import asyncio

from modules.logger import timing


def test_timed_log_wraps_sync_function(monkeypatch):
    events = []
    monkeypatch.setattr(
        timing,
        "log_timing",
        lambda event, duration_sec=None, **details: events.append(
            (event, duration_sec, details)
        ),
    )

    @timing.timed_log("sample.sync", source="test")
    def sample():
        return "ok"

    assert sample() == "ok"
    assert events[0][0] == "sample.sync"
    assert events[0][1] >= 0
    assert events[0][2] == {"source": "test"}


def test_timed_log_wraps_async_function(monkeypatch):
    events = []
    monkeypatch.setattr(
        timing,
        "log_timing",
        lambda event, duration_sec=None, **details: events.append(
            (event, duration_sec, details)
        ),
    )

    @timing.timed_log("sample.async")
    async def sample():
        return "ok"

    assert asyncio.run(sample()) == "ok"
    assert events[0][0] == "sample.async"
    assert events[0][1] >= 0
