import asyncio
import multiprocessing

import pytest

from car2lego3d.image_slots import IMAGE_CONCURRENCY, image_slot, release, try_acquire


def acquire_in_process(directory, result):
    stream = try_acquire(directory)
    result.put(stream is not None)
    if stream is not None:
        release(stream)


def test_requests_in_another_process_observe_all_five_occupied_slots(tmp_path):
    streams = [try_acquire(tmp_path) for _ in range(IMAGE_CONCURRENCY)]
    assert all(streams)
    context = multiprocessing.get_context("spawn")
    result = context.Queue()
    try:
        child = context.Process(target=acquire_in_process, args=(str(tmp_path), result))
        child.start()
        assert result.get(timeout=10) is False
        child.join(timeout=10)
        assert child.exitcode == 0
        release(streams.pop())
        child = context.Process(target=acquire_in_process, args=(str(tmp_path), result))
        child.start()
        assert result.get(timeout=10) is True
        child.join(timeout=10)
        assert child.exitcode == 0
    finally:
        for stream in streams:
            release(stream)
        result.close()


def test_cancelled_request_releases_slot_and_waiting_does_not_time_out(tmp_path):
    async def run():
        entered, finish = asyncio.Event(), asyncio.Event()

        async def request():
            async with image_slot(tmp_path, poll_interval=.005):
                entered.set()
                await finish.wait()

        streams = [try_acquire(tmp_path) for _ in range(IMAGE_CONCURRENCY)]
        task = asyncio.create_task(request())
        try:
            await asyncio.sleep(.03)
            assert not entered.is_set()
            release(streams.pop())
            await asyncio.wait_for(entered.wait(), timeout=2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            replacement = try_acquire(tmp_path)
            assert replacement is not None
            release(replacement)
        finally:
            task.cancel()
            for stream in streams:
                release(stream)

    asyncio.run(run())
