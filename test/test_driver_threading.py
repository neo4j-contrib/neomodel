"""
Regression tests for the process-wide driver introduced when connection state
was moved off ContextVars.

A freshly spawned OS thread starts with default context-var values, so before
the driver became a plain attribute on the singleton, such a thread would see
``db.driver is None`` and silently build its own driver (and connection pool).
These tests assert the driver is now shared across threads and is not rebuilt.

This is intentionally a hand-written sync test (not transpiled): the scenario it
guards - neomodel used from a thread pool, sync Celery/gunicorn workers, etc. -
is specific to the threaded world.
"""

import threading

from neomodel import db


def test_driver_is_shared_across_threads():
    # Establish the process-wide connection in the main thread.
    db.cypher_query("RETURN 1")
    main_driver = db.driver
    assert main_driver is not None

    observed: dict[str, object] = {}

    def worker() -> None:
        # A fresh thread starts with default context-vars: it must still observe
        # the shared driver, not None.
        observed["before_query"] = db.driver
        # Running a query must reuse that driver, not build a new one.
        db.cypher_query("RETURN 1")
        observed["after_query"] = db.driver

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    assert observed["before_query"] is main_driver
    assert observed["after_query"] is main_driver
    assert db.driver is main_driver


def test_concurrent_first_use_builds_single_driver():
    # Start from a disconnected state so every worker hits the lazy-connect path
    # in ensure_connection at once.
    db.close_connection()

    barrier = threading.Barrier(5)
    drivers: list[object] = []
    lock = threading.Lock()

    def worker() -> None:
        # Maximise contention on the lazy-build path.
        barrier.wait()
        db.cypher_query("RETURN 1")
        with lock:
            drivers.append(db.driver)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # All workers must end up sharing one driver instance.
    assert drivers, "no driver was observed"
    assert all(driver is db.driver for driver in drivers)
    assert len(set(id(driver) for driver in drivers)) == 1
