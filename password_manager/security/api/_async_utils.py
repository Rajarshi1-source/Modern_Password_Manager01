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

# A BACKSTOP, not a budget: every current caller already bounds itself
# internally (the NOAA client's httpx timeout=30s, CosmicWatchClient.
# collect_events' own timeout_seconds, the simulator's non-realistic-timing
# path), so under normal operation this ceiling is never approached. It
# exists only so the Django request thread is guaranteed to be released even
# if a future caller -- or an edit to an existing one -- forgets to bound
# itself, or a dependency hangs past its own configured timeout (e.g. an OS
# level TCP stall past httpx's budget). Set well above the worst legitimate
# duration actually traced through this helper: a cold, uncached
# get_healthy_buoys() sweep can sequentially probe every registered NOAA
# buoy at up to httpx's 30s each.
DEFAULT_TIMEOUT_SECONDS = 120


def run_async(coro, timeout: float = DEFAULT_TIMEOUT_SECONDS):
    """Run an async coroutine from a synchronous view, with an outer bound.

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

    ``asyncio.TimeoutError`` on expiry is not caught here: every current call
    site already sits inside its own ``except Exception`` (view-level), which
    turns it into the same graceful failure response any other error gets —
    no new error-handling path needed at any of the 16 call sites this wraps.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # Nothing running on this thread — the normal sync-view case.
        return asyncio.run(asyncio.wait_for(coro, timeout=timeout))
    # Already inside a running loop: ``run_until_complete`` would raise "This
    # event loop is already running", and blocking it would deadlock. Hand the
    # coroutine to a worker thread that owns its own loop.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, asyncio.wait_for(coro, timeout=timeout)).result()
