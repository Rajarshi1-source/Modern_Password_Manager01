"""
Tests for the shared sync/async bridge (security.api._async_utils)
=====================================================================

Regression coverage for PR #454 review round 19: run_async() had no bound on
the coroutine it ran, so a hung dependency could block a Django request
thread forever. These tests exercise the fix directly against the shared
helper rather than through any one of its 16 call sites.

@author Password Manager Team
@created 2026-08-01
"""

import asyncio
import time

from django.test import SimpleTestCase

from security.api._async_utils import run_async


class RunAsyncTests(SimpleTestCase):
    """`run_async` bounds execution without disturbing the normal path."""

    def test_fast_coroutine_returns_normally(self):
        async def fast():
            await asyncio.sleep(0)
            return 'ok'

        self.assertEqual(run_async(fast()), 'ok')

    def test_hung_coroutine_is_bounded_not_infinite(self):
        """A coroutine that never completes must still release the caller.

        This is the actual regression: without asyncio.wait_for, this call
        would block for the full asyncio.sleep(999) -- effectively forever
        from a Django request's perspective.
        """
        async def hangs():
            await asyncio.sleep(999)
            return 'never'

        start = time.monotonic()
        with self.assertRaises((asyncio.TimeoutError, TimeoutError)):
            run_async(hangs(), timeout=0.2)
        elapsed = time.monotonic() - start

        self.assertLess(elapsed, 5.0, "the timeout did not actually bound execution")

    def test_application_errors_still_propagate_unchanged(self):
        """Wrapping in asyncio.wait_for must not mask a real exception."""
        async def app_error():
            raise RuntimeError('a real application error')

        with self.assertRaises(RuntimeError) as ctx:
            run_async(app_error())
        self.assertEqual(str(ctx.exception), 'a real application error')

    def test_default_timeout_exceeds_every_traced_worst_case(self):
        """The default must stay generous enough not to truncate a legitimate
        cold get_healthy_buoys() sweep (traced worst case: all 14 registered
        buoys x httpx's 30s timeout each = 420s). Pinned so a future edit
        cannot quietly shrink it below what real callers need without a
        deliberate decision.
        """
        from security.api._async_utils import DEFAULT_TIMEOUT_SECONDS
        self.assertGreaterEqual(DEFAULT_TIMEOUT_SECONDS, 420)

    def test_works_from_inside_an_already_running_loop(self):
        """The nested case (called from async code) must not deadlock."""
        async def fast():
            await asyncio.sleep(0)
            return 'ok'

        async def outer():
            return run_async(fast())

        self.assertEqual(asyncio.run(outer()), 'ok')
