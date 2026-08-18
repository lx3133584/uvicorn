from __future__ import annotations

import asyncio
import threading

from uvicorn import Config
from uvicorn._types import ASGIReceiveCallable, ASGISendCallable, Scope
from uvicorn.supervisors.process import Process


async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
    pass  # pragma: no cover


async def slow_startup_app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
    assert scope["type"] == "lifespan"

    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await asyncio.sleep(0.5)
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


def test_process_ping_pong() -> None:
    process = Process(Config(app=app), sockets=[])
    process.start()
    assert process.wait_until_ready(5)
    assert process.ping()
    process.terminate()
    process.join()


def test_process_ping_pong_timeout() -> None:
    process = Process(Config(app=app), sockets=[])
    assert not process.ping(0.1)
    process.parent_conn.close()
    process.child_conn.close()


def test_process_ping_broken_pipe() -> None:
    process = Process(Config(app=app), sockets=[])
    process.parent_conn.close()
    process.child_conn.close()
    assert not process.ping(0.1)
    process.terminate()


def test_process_exits_when_control_pipe_closes() -> None:
    process = Process(Config(app=app), sockets=[])
    process.start()
    assert process.wait_until_ready(5)

    process.parent_conn.close()
    process.join()

    assert process.exitcode == 0


def test_process_ready() -> None:
    process = Process(Config(app=slow_startup_app), sockets=[])
    process.start()

    assert process.ping()
    assert not process.is_ready()
    assert process.wait_until_ready(5)

    process.terminate()
    process.join()


def test_wait_until_ready_bails_on_shutdown_or_dead_worker() -> None:
    process = Process(Config(app=app), sockets=[])

    should_exit = threading.Event()
    should_exit.set()
    assert process.wait_until_ready(timeout=1, should_exit=should_exit) is False
    assert process.wait_until_ready(timeout=0.5) is False

    process.parent_conn.close()
    process.child_conn.close()
