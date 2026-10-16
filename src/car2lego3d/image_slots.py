"""Process-shared image request slots, released by the OS after a worker exits."""
import asyncio
from contextlib import asynccontextmanager
import errno
import os
from pathlib import Path
import tempfile


IMAGE_CONCURRENCY = 5


def slot_directory():
    return Path(tempfile.gettempdir()) / "car2lego3d-image-slots-v1"


def try_acquire(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for index in range(IMAGE_CONCURRENCY):
        stream = (directory / f"request-{index}.lock").open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                if stream.seek(0, os.SEEK_END) == 0:
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return stream
        except OSError as error:
            stream.close()
            if error.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise
    return None


def release(stream):
    try:
        if os.name == "nt":
            import msvcrt
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    finally:
        stream.close()


@asynccontextmanager
async def image_slot(directory=None, poll_interval=.25):
    # Lock only the actual SDK request, not reference analysis, cache reads or backoff.
    stream = None
    try:
        while stream is None:
            stream = try_acquire(directory if directory is not None else slot_directory())
            if stream is None:
                await asyncio.sleep(poll_interval)
        yield
    finally:
        if stream is not None:
            release(stream)
