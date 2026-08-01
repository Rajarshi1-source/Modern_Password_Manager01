"""
Sync/async bridge for DRF views
=================================

One `run_async` shared by every view module that wraps an async service call
in a synchronous DRF view. Previously implemented independently three times
(ocean_entropy_views, storm_chase_views, cosmic_ray_views); the logic is easy
to get subtly wrong -- see the docstring below -- so a fix landing in only one
or two copies was a real risk that already happened once.
"""

import asyncio
import concurrent.futures


def run_async(coro):
    """Run an async coroutine from a synchronous view.

    ``get_running_loop()`` rather than ``get_event_loop()``: the latter hands
    back whatever loop was last SET on this thread, which may already be
    CLOSED ("Event loop is closed"), and on Python 3.12+ raises when nothing is
    set — precisely the state ``asyncio.run()`` leaves behind. So any earlier
    caller using ``asyncio.run`` (``StormChaseService._run_coro``, the NOAA
    integration tests) broke the next view to run on that thread.
    ``get_running_loop()`` only ever reports a loop that is genuinely running
    here, so a stale or closed one cannot be picked up at all.

    ``asyncio.run`` also CLOSES the loop it creates; a ``new_event_loop()`` +
    ``set_event_loop()`` fallback would leak one loop per call and leave it
    installed for whatever ran next.

    Note the coroutine is never executed inside a ``try/except RuntimeError``:
    doing so swallows genuine application errors and, since the coroutine has
    already been consumed by then, reports the misleading "cannot reuse already
    awaited coroutine" in their place.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # Nothing running on this thread — the normal sync-view case.
        return asyncio.run(coro)
    # Already inside a running loop: ``run_until_complete`` would raise "This
    # event loop is already running", and blocking it would deadlock. Hand the
    # coroutine to a worker thread that owns its own loop.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()
