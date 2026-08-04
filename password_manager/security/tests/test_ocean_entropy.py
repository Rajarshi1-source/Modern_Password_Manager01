"""
Ocean Wave Entropy Tests (Enhanced)
=====================================

Comprehensive test suite for ocean wave entropy harvesting.
Tests cover:
- NOAA buoy client with mocking
- BuoyReading methods (to_entropy_bytes, entropy_quality_score)
- Entropy extraction algorithms
- HybridEntropyGenerator
- API endpoints
- Django models

@author Password Manager Team
@created 2026-01-23
"""

import pytest
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio
import struct
import hashlib

User = get_user_model()


# =============================================================================
# BuoyReading Tests
# =============================================================================

class TestBuoyReading(TestCase):
    """Tests for BuoyReading dataclass methods."""
    
    def setUp(self):
        """Create test buoy reading."""
        from security.services.noaa_api_client import BuoyReading
        
        self.complete_reading = BuoyReading(
            buoy_id='44013',
            timestamp=datetime.utcnow(),
            wave_height_m=2.35,
            wave_period_sec=8.2,
            wave_direction_deg=285,
            wind_speed_mps=5.5,
            wind_gust_mps=7.8,
            wind_direction_deg=290,
            pressure_hpa=1013.25,
            air_temp_c=22.5,
            sea_temp_c=18.3,
            latitude=42.346,
            longitude=-70.651,
        )
        
        self.incomplete_reading = BuoyReading(
            buoy_id='44025',
            timestamp=datetime.utcnow(),
            wave_height_m=1.5,
            wave_period_sec=None,
            wave_direction_deg=None,
        )
    
    def test_to_entropy_bytes_returns_64_bytes(self):
        """Test that to_entropy_bytes returns SHA3-512 hash (64 bytes)."""
        entropy = self.complete_reading.to_entropy_bytes()
        
        self.assertEqual(len(entropy), 64)
        self.assertIsInstance(entropy, bytes)
    
    def test_to_entropy_bytes_is_deterministic(self):
        """Test that same reading produces same entropy."""
        entropy1 = self.complete_reading.to_entropy_bytes()
        entropy2 = self.complete_reading.to_entropy_bytes()
        
        self.assertEqual(entropy1, entropy2)
    
    def test_to_entropy_bytes_varies_with_data(self):
        """Test that different readings produce different entropy."""
        entropy1 = self.complete_reading.to_entropy_bytes()
        entropy2 = self.incomplete_reading.to_entropy_bytes()
        
        self.assertNotEqual(entropy1, entropy2)
    
    def test_entropy_quality_score_complete_reading(self):
        """Test quality score for complete reading (high score)."""
        score = self.complete_reading.entropy_quality_score
        
        self.assertGreater(score, 0.8)
        self.assertLessEqual(score, 1.0)
    
    def test_entropy_quality_score_incomplete_reading(self):
        """Test quality score for incomplete reading (lower score)."""
        score = self.incomplete_reading.entropy_quality_score
        
        self.assertLess(score, 0.5)
        self.assertGreaterEqual(score, 0.0)
    
    def test_entropy_quality_score_wave_bonus(self):
        """Test that high waves give quality bonus."""
        from security.services.noaa_api_client import BuoyReading
        
        low_wave = BuoyReading(
            buoy_id='test',
            timestamp=datetime.utcnow(),
            wave_height_m=0.5,
        )
        
        high_wave = BuoyReading(
            buoy_id='test',
            timestamp=datetime.utcnow(),
            wave_height_m=5.0,
        )
        
        # High waves should have higher score
        self.assertGreater(high_wave.entropy_quality_score, low_wave.entropy_quality_score)
    
    def test_to_dict_includes_quality_score(self):
        """Test that to_dict includes quality_score."""
        data = self.complete_reading.to_dict()
        
        self.assertIn('quality_score', data)
        self.assertIn('latitude', data)
        self.assertIn('longitude', data)


# =============================================================================
# Entropy Extractor Tests
# =============================================================================

class TestEntropyExtractor(TestCase):
    """Tests for entropy extraction algorithms."""
    
    def test_extract_lsb_bits(self):
        """Test LSB extraction from floating point values."""
        from security.services.ocean_wave_entropy_service import EntropyExtractor
        
        bits = EntropyExtractor.extract_lsb_bits(3.14159, num_bits=8)
        
        self.assertEqual(len(bits), 8)
        self.assertTrue(all(b in [0, 1] for b in bits))
    
    def test_extract_lsb_bits_none_value(self):
        """Test LSB extraction with None value."""
        from security.services.ocean_wave_entropy_service import EntropyExtractor
        
        bits = EntropyExtractor.extract_lsb_bits(None, num_bits=8)
        
        self.assertEqual(bits, [])
    
    def test_von_neumann_debias(self):
        """Test von Neumann debiasing algorithm."""
        from security.services.ocean_wave_entropy_service import EntropyExtractor
        
        # 01 -> 0, 10 -> 1, 00 -> discard, 11 -> discard
        input_bits = [0, 1, 1, 0, 0, 0, 1, 1, 0, 1]
        
        debiased = EntropyExtractor.von_neumann_debias(input_bits)
        
        self.assertEqual(debiased, [0, 1, 0])
    
    def test_bits_to_bytes(self):
        """Test bit array to bytes conversion."""
        from security.services.ocean_wave_entropy_service import EntropyExtractor
        
        bits = [1, 0, 1, 0, 1, 0, 1, 0]  # = 170 (0xAA)
        
        result = EntropyExtractor.bits_to_bytes(bits)
        
        self.assertEqual(result, bytes([170]))
    
    def test_estimate_min_entropy(self):
        """Test min-entropy estimation."""
        from security.services.ocean_wave_entropy_service import EntropyExtractor
        
        # Uniform data should have high entropy
        uniform_data = bytes(range(256))
        min_entropy = EntropyExtractor.estimate_min_entropy(uniform_data)
        
        self.assertGreater(min_entropy, 7.5)
    
    def test_estimate_min_entropy_low(self):
        """Test min-entropy estimation with low entropy data."""
        from security.services.ocean_wave_entropy_service import EntropyExtractor
        
        constant_data = bytes([42] * 100)
        min_entropy = EntropyExtractor.estimate_min_entropy(constant_data)
        
        self.assertEqual(min_entropy, 0.0)


# =============================================================================
# assess_entropy_quality Tests
# =============================================================================

class TestAssessEntropyQuality(TestCase):
    """Tests for entropy quality assessment."""
    
    def test_assess_high_quality_entropy(self):
        """Test assessment of high-quality random data."""
        from security.services.ocean_wave_entropy_service import assess_entropy_quality
        import secrets
        
        high_quality = secrets.token_bytes(256)
        assessment = assess_entropy_quality(high_quality)
        
        # Shannon entropy of 256 random bytes hovers near but under 1.0 in
        # practice (~0.89); relax the threshold to avoid flakiness.
        self.assertGreater(assessment['entropy_ratio'], 0.85)
        self.assertIn(assessment['quality'], ('good', 'excellent'))
        self.assertIn('shannon_entropy', assessment)
        self.assertIn('chi_squared', assessment)
        self.assertIn('runs', assessment)
    
    def test_assess_poor_quality_entropy(self):
        """Test assessment of poor-quality data."""
        from security.services.ocean_wave_entropy_service import assess_entropy_quality
        
        poor_quality = bytes([0] * 256)
        assessment = assess_entropy_quality(poor_quality)
        
        self.assertEqual(assessment['quality'], 'poor')
        self.assertLess(assessment['entropy_ratio'], 0.5)
    
    def test_assess_empty_data(self):
        """Test assessment of empty data."""
        from security.services.ocean_wave_entropy_service import assess_entropy_quality
        
        assessment = assess_entropy_quality(b'')
        
        self.assertEqual(assessment['quality'], 'poor')
        self.assertEqual(assessment['entropy_ratio'], 0.0)


# =============================================================================
# Exceptions Tests
# =============================================================================

class TestExceptions(TestCase):
    """Tests for custom exceptions."""
    
    def test_entropy_unavailable_exception(self):
        """Test EntropyUnavailable exception."""
        from security.services.ocean_wave_entropy_service import EntropyUnavailable
        
        with self.assertRaises(EntropyUnavailable):
            raise EntropyUnavailable("No buoys available")
    
    def test_insufficient_entropy_sources_exception(self):
        """Test InsufficientEntropySources exception."""
        from security.services.ocean_wave_entropy_service import InsufficientEntropySources
        
        with self.assertRaises(InsufficientEntropySources):
            raise InsufficientEntropySources("Only 1 source available")


# =============================================================================
# EntropyMixer Tests
# =============================================================================

class TestEntropyMixer(TestCase):
    """Tests for multi-source entropy mixing."""
    
    def test_mix_two_sources(self):
        """Test mixing two entropy sources."""
        from security.services.ocean_wave_entropy_service import EntropyMixer
        
        source1 = bytes([0xAA] * 32)
        source2 = bytes([0x55] * 32)
        
        mixed = EntropyMixer.mix_sources(source1, source2)
        
        self.assertEqual(len(mixed), 32)
        self.assertNotEqual(mixed, source1)
        self.assertNotEqual(mixed, source2)
    
    def test_mix_single_source(self):
        """Test mixing with single source returns original."""
        from security.services.ocean_wave_entropy_service import EntropyMixer
        
        source = bytes([0xAA] * 32)
        mixed = EntropyMixer.mix_sources(source)
        
        self.assertEqual(mixed, source)
    
    def test_mix_empty_raises(self):
        """Test mixing with no sources raises error."""
        from security.services.ocean_wave_entropy_service import EntropyMixer
        
        with self.assertRaises(ValueError):
            EntropyMixer.mix_sources()
    
    def test_weighted_mix(self):
        """Test weighted mixing of sources."""
        from security.services.ocean_wave_entropy_service import EntropyMixer
        
        sources = {
            'quantum': (bytes([0x11] * 32), 0.9),
            'ocean': (bytes([0x22] * 32), 0.7),
        }
        
        mixed = EntropyMixer.weighted_mix(sources)
        
        self.assertEqual(len(mixed), 32)


# =============================================================================
# HybridEntropyGenerator Tests
# =============================================================================

class TestHybridEntropyGenerator(TestCase):
    """Tests for HybridEntropyGenerator."""
    
    def test_generator_initialization(self):
        """Test generator can be initialized."""
        from security.services.ocean_wave_entropy_service import HybridEntropyGenerator
        
        generator = HybridEntropyGenerator()
        
        self.assertIsNotNone(generator.ocean_provider)
        self.assertEqual(generator.mix_history, [])
    
    def test_get_audit_trail(self):
        """Test audit trail retrieval."""
        from security.services.ocean_wave_entropy_service import HybridEntropyGenerator
        
        generator = HybridEntropyGenerator()
        trail = generator.get_audit_trail()
        
        self.assertIsInstance(trail, list)


# =============================================================================
# NOAA Client Tests with Mocking
# =============================================================================

class TestNOAABuoyClientMocked(TestCase):
    """Tests for NOAA buoy client with mocked HTTP."""
    
    def test_parse_realtime2_format(self):
        """Test parsing of realtime2 data format."""
        from security.services.noaa_api_client import NOAABuoyClient
        
        client = NOAABuoyClient()
        
        sample_data = """#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE
#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft
2024 07 15 10 00 120 5.2  6.1  1.5   8.0   5.3 135 1015.2 22.3 24.1 20.5 10.0 +0.2  MM
"""
        
        reading = client._parse_realtime2('44013', sample_data)
        
        self.assertIsNotNone(reading)
        self.assertEqual(reading.buoy_id, '44013')
        self.assertEqual(reading.wind_direction_deg, 120)
        self.assertEqual(reading.wind_speed_mps, 5.2)
        self.assertEqual(reading.wind_gust_mps, 6.1)
        self.assertEqual(reading.wave_height_m, 1.5)
        self.assertEqual(reading.wave_period_sec, 8.0)
    
    def test_parse_realtime2_missing_values(self):
        """Test parsing handles MM (missing) values."""
        from security.services.noaa_api_client import NOAABuoyClient
        
        client = NOAABuoyClient()
        
        sample_data = """#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE
#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft
2024 07 15 10 00 MM   5.2  MM   1.5   MM    5.3 MM  1015.2 MM   24.1 20.5 MM   MM   MM"""
        
        reading = client._parse_realtime2('44013', sample_data)
        
        self.assertIsNotNone(reading)
        self.assertIsNone(reading.wind_direction_deg)
        self.assertEqual(reading.wind_speed_mps, 5.2)
        self.assertIsNone(reading.wind_gust_mps)
        self.assertEqual(reading.wave_height_m, 1.5)
    
    def test_parse_empty_data(self):
        """Test parsing empty data returns None."""
        from security.services.noaa_api_client import NOAABuoyClient
        
        client = NOAABuoyClient()
        reading = client._parse_realtime2('44013', '')
        
        self.assertIsNone(reading)
    
    def test_get_region_for_hour(self):
        """Test region rotation by hour."""
        from security.services.noaa_api_client import NOAABuoyClient
        
        client = NOAABuoyClient()
        
        regions_seen = set()
        for hour in range(24):
            region = client.get_region_for_hour(hour)
            regions_seen.add(region)

        self.assertGreater(len(regions_seen), 1)


class NOAAClientLoopSafetyTests(TestCase):
    """`_get_client` rotates safely across event loops and under contention.

    Regression coverage for two rounds of PR #454 review:
      * a client cached across `asyncio.run()` calls raised "Event loop is
        closed" / "<Event> is bound to a different event loop" (fixed by
        tracking the loop the client was built on);
      * `fetch_multiple_buoys` calls `_get_client()` from several concurrent
        coroutines under one semaphore, and the ORIGINAL fix for the above
        awaited the stale client's `.aclose()` before publishing the
        replacement — leaving a window where multiple racing coroutines each
        saw the same stale client, each built their OWN replacement, and
        overwrote one another (leaking every replacement but the last).
    """

    def _client_and_fake_stale(self):
        import asyncio
        from security.services.noaa_api_client import NOAABuoyClient

        client = NOAABuoyClient()

        class _FakeClient:
            def __init__(self):
                self.is_closed = False
                self.close_calls = 0

            async def aclose(self):
                await asyncio.sleep(0)  # force a real yield, like the real one
                self.is_closed = True
                self.close_calls += 1

        stale = _FakeClient()
        client._client = stale
        client._client_loop = None  # different from the loop about to run
        return client, stale

    def test_rotates_to_a_fresh_client_per_loop(self):
        """A new asyncio.run() must not reuse a client from a prior loop."""
        import asyncio
        from security.services import noaa_api_client as noaa_module
        from security.services.noaa_api_client import NOAABuoyClient

        class _FakeClient:
            def __init__(self, **kwargs):
                self.is_closed = False

            async def aclose(self):
                self.is_closed = True

        client = NOAABuoyClient()
        # Hold the client OBJECTS, and only then compare identities. Taking
        # id() of a value that is discarded immediately is unsound: CPython
        # reuses the address of a freed object, so two genuinely different
        # clients can report the same id() and the assertion fails for a
        # reason that has nothing to do with the behaviour under test.
        #
        # Patched so this builds fake clients instead of real httpx.AsyncClient
        # instances -- unpatched, each would open a real connection pool that
        # nothing in this test ever closes.
        with patch.object(noaa_module.httpx, 'AsyncClient', _FakeClient):
            seen = [asyncio.run(client._get_client()) for _ in range(3)]
        self.assertEqual(
            len({id(c) for c in seen}), 3, "each asyncio.run() must get its own client",
        )

    def test_reuses_the_same_client_within_one_loop(self):
        """Multiple calls inside ONE loop must share a single client."""
        import asyncio
        from security.services.noaa_api_client import NOAABuoyClient

        client = NOAABuoyClient()

        async def three_calls():
            a = await client._get_client()
            b = await client._get_client()
            c = await client._get_client()
            return id(a), id(b), id(c)

        a, b, c = asyncio.run(three_calls())
        self.assertEqual(a, b)
        self.assertEqual(b, c)

    def test_concurrent_callers_do_not_race_the_replacement(self):
        """8 coroutines racing _get_client() must converge on ONE new client.

        Reproduces fetch_multiple_buoys's concurrency shape directly against
        `_get_client()` rather than the network, so it is deterministic.
        """
        import asyncio
        from security.services import noaa_api_client as noaa_module

        client, stale = self._client_and_fake_stale()

        class _FakeClient:
            def __init__(self, **kwargs):
                self.is_closed = False

            async def aclose(self):
                self.is_closed = True

        async def hammer():
            return await asyncio.gather(*[client._get_client() for _ in range(8)])

        # Patched for the same reason as test_rotates_to_a_fresh_client_per_loop:
        # without it, the winning replacement is a real httpx.AsyncClient that
        # this test never closes.
        with patch.object(noaa_module.httpx, 'AsyncClient', _FakeClient):
            results = asyncio.run(hammer())
        self.assertEqual(
            len({id(r) for r in results}), 1,
            "concurrent callers received different replacement clients",
        )
        self.assertEqual(stale.close_calls, 1, "the stale client must be closed exactly once")

    def test_client_replacement_is_mutually_exclusive_across_threads(self):
        """Only ONE thread at a time may be inside the replacement block.

        The tests above all run on a single loop, where "statements up to the
        first await cannot interleave" makes the check-and-store effectively
        atomic. That argument says nothing about a second THREAD running its
        own loop — the ordinary production shape, since `get_noaa_client()` is
        a process-wide singleton and sync Django views reach it through
        `run_async` -> `asyncio.run` on a worker thread per request. Unguarded,
        two threads interleave the `_client` / `_client_loop` stores and can
        leave the pair describing DIFFERENT loops, handing a later caller a
        client bound to a loop it is not running on — the exact "bound to a
        different event loop" failure the loop tracking exists to prevent.

        Asserted via mutual exclusion rather than by racing for a corrupted
        result: the vulnerable window is a couple of bytecodes, so the GIL
        almost never preempts inside it and a race-and-hope test passes just
        as happily on unguarded code. Making the client constructor slow turns
        the property into a deterministic one — without the lock every thread
        is inside the block at once, with it exactly one is.
        """
        import asyncio
        import threading
        import time
        from security.services import noaa_api_client as noaa_module

        threads = 6
        inside = 0
        peak = 0
        counter_lock = threading.Lock()

        class _SlowClient:
            """Stands in for httpx.AsyncClient, wide enough to observe overlap."""

            def __init__(self, **kwargs):
                nonlocal inside, peak
                with counter_lock:
                    inside += 1
                    peak = max(peak, inside)
                time.sleep(0.05)
                with counter_lock:
                    inside -= 1
                self.is_closed = False

            async def aclose(self):
                self.is_closed = True

        client = noaa_module.NOAABuoyClient()
        # Bounded: an unbounded barrier hangs every other thread forever if one
        # dies before reaching wait(), turning a bug into a stuck CI job
        # instead of a failing test.
        barrier = threading.Barrier(threads, timeout=10)
        errors = []

        def worker():
            async def main():
                barrier.wait()          # all threads enter together
                return await client._get_client()
            try:
                asyncio.run(main())
            except Exception as exc:  # noqa: BLE001 - surfaced on the main thread below
                errors.append(exc)

        with patch.object(noaa_module.httpx, 'AsyncClient', _SlowClient):
            workers = [threading.Thread(target=worker) for _ in range(threads)]
            for t in workers:
                t.start()
            for t in workers:
                t.join()

        self.assertEqual(errors, [], f"worker threads failed: {errors}")
        self.assertEqual(
            peak, 1,
            f"{peak} threads were inside the client-replacement block at once; "
            "the check and the store are not atomic across threads",
        )

    def test_close_and_get_client_are_mutually_exclusive_across_threads(self):
        """close() must hold the SAME lock as _get_client(), not just call it.

        A first version of this test (since corrected) drove both coroutines
        through `asyncio.gather` on one loop and asserted a fresh client
        survives a concurrent `close()`. CodeRabbit caught that its own setup
        (`old.is_closed = True`) made `close()` skip its await entirely, so
        `closer()` finished before `getter()` ever started -- no interleaving
        occurred, and the assertion held vacuously. Investigating further:
        even with that line removed, the assertion holds unconditionally
        given how close() orders its writes (detach-then-await, matching
        _get_client()'s publish-before-await) -- on ONE event loop, three
        plain attribute writes with no `await` between them cannot be
        interleaved by another coroutine regardless of locking. So a same-loop
        test cannot exercise what `_client_lock` in close() actually guards:
        CROSS-THREAD safety, the same category round 22 established for
        `_get_client()` alone -- close() and a concurrent `_get_client()` on a
        DIFFERENT thread's loop must not interleave their reads/writes of
        `_client` / `_client_loop`.

        Verified via mutual exclusion, not a race for a corrupted result, for
        the same reason as round 22: the vulnerable window is a handful of
        bytecodes, so an unguarded race can pass by luck. `_get_client()`'s
        replacement block is made artificially slow (there is nothing to slow
        down inside close()'s own three-line body); if the lock is shared,
        close() running on another thread must block for the ENTIRE slow
        window before it can even start, not just happen not to corrupt
        anything.
        """
        import asyncio
        import threading
        import time
        from security.services import noaa_api_client as noaa_module

        constructing = threading.Event()

        class _SlowClient:
            def __init__(self, **kwargs):
                # Set INSIDE _get_client()'s critical section (this
                # constructor only runs while it holds _client_lock), so
                # waiting on this proves the getter thread has actually
                # ACQUIRED the lock -- not merely that its thread has started.
                # A fixed sleep-then-race here would be a timing guess: on a
                # loaded runner, close() could win the lock first and return
                # fast, failing the assertion below for a scheduling reason
                # that has nothing to do with whether the lock is shared.
                constructing.set()
                time.sleep(0.15)
                self.is_closed = False

            async def aclose(self):
                self.is_closed = True

        client = noaa_module.NOAABuoyClient()
        client._client = None
        client._client_loop = None

        def get_client_worker():
            async def main():
                return await client._get_client()
            asyncio.run(main())

        with patch.object(noaa_module.httpx, 'AsyncClient', _SlowClient):
            t = threading.Thread(target=get_client_worker)
            t.start()
            self.assertTrue(
                constructing.wait(timeout=5),
                "_get_client() never entered its replacement block",
            )

            # Loop creation/teardown is not part of what this test measures --
            # asyncio.run() does both inside its call, which would otherwise
            # eat into the tight margin between the 0.05s threshold and the
            # getter thread's 0.15s construction window on a loaded runner.
            # close() has no cross-loop dependency of its own (unlike
            # _get_client(), it does not track which loop it ran on), so a
            # loop built here and never installed as "current" is equivalent.
            loop = asyncio.new_event_loop()
            try:
                start = time.monotonic()
                loop.run_until_complete(client.close())
                elapsed = time.monotonic() - start
            finally:
                loop.close()

            t.join(timeout=5)
            self.assertFalse(t.is_alive(), "_get_client() thread did not finish")

        self.assertGreater(
            elapsed, 0.05,
            f"close() returned after {elapsed:.3f}s while _get_client() should "
            "still have been holding the lock for its slow client construction "
            "-- close() is not actually serialized against it",
        )


# =============================================================================
# Buoy Registry Tests
# =============================================================================

class TestBuoyRegistry(TestCase):
    """Tests for buoy registry."""
    
    def test_all_buoys_registered(self):
        """Test all buoys are in the registry."""
        from security.services.noaa_api_client import ALL_BUOYS, PRIORITY_BUOYS
        
        total_priority = sum(len(buoys) for buoys in PRIORITY_BUOYS.values())
        
        self.assertEqual(len(ALL_BUOYS), total_priority)
    
    def test_regions_have_buoys(self):
        """Test all regions have at least one buoy."""
        from security.services.noaa_api_client import PRIORITY_BUOYS
        
        expected_regions = ['atlantic', 'pacific', 'gulf', 'caribbean']
        
        for region in expected_regions:
            self.assertIn(region, PRIORITY_BUOYS)
            self.assertGreater(len(PRIORITY_BUOYS[region]), 0)


# =============================================================================
# API Endpoint Tests
# =============================================================================

class TestOceanEntropyAPI(TestCase):
    """Tests for ocean entropy API endpoints."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)
    
    def test_buoy_list_endpoint(self):
        """Test buoy list endpoint returns data."""
        response = self.client.get('/api/security/ocean/buoys/')
        
        # May fail without auth, but should not be 500
        self.assertIn(response.status_code, [200, 401, 403])
    
    def test_status_endpoint(self):
        """Test ocean status endpoint."""
        response = self.client.get('/api/security/ocean/status/')
        
        self.assertIn(response.status_code, [200, 401, 403, 503])


# =============================================================================
# Django Model Tests
# =============================================================================

class TestOceanEntropyModels(TestCase):
    """Tests for ocean entropy Django models."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_ocean_entropy_batch_creation(self):
        """Test OceanEntropyBatch model."""
        try:
            from security.models.ocean_entropy_models import OceanEntropyBatch
            
            batch = OceanEntropyBatch.objects.create(
                buoy_id='44013',
                buoy_name='Boston Buoy',
                buoy_latitude=Decimal('42.346'),
                buoy_longitude=Decimal('-70.651'),
                wave_height=2.3,
                wave_period=8.2,
                water_temperature=15.5,
                wind_speed=8.5,
                bytes_fetched=64,
                quality_score=0.9,
                # Use timezone-aware "now" — Django's USE_TZ=True
                # rejects naive datetimes with a RuntimeWarning.
                buoy_reading_timestamp=timezone.now(),
            )
            
            self.assertEqual(batch.buoy_id, '44013')
            self.assertEqual(batch.bytes_fetched, 64)
            self.assertEqual(str(batch.buoy_latitude), '42.346')
        except ImportError:
            self.skipTest("Models not yet migrated")
    
    def test_hybrid_password_certificate_creation(self):
        """Test HybridPasswordCertificate model."""
        try:
            from security.models.ocean_entropy_models import HybridPasswordCertificate
            
            cert = HybridPasswordCertificate.objects.create(
                user=self.user,
                password_hash_prefix='test_hash_prefix_safe',  # pragma: allowlist secret
                sources_used=['quantum', 'ocean'],
                quantum_provider='ANU',
                ocean_buoy_id='44013',
                ocean_wave_height=2.3,
                mixing_algorithm='XOR + SHA3-512 + SHAKE256',
                total_entropy_bits=128,
                password_length=16,
                combined_quality_score=0.95,
                signature='sig123abc456',
            )
            
            self.assertEqual(cert.user, self.user)
            self.assertEqual(len(cert.sources_used), 2)
            
            # Test to_dict
            cert_dict = cert.to_dict()
            self.assertEqual(cert_dict['ocean']['buoy_id'], '44013')
        except ImportError:
            self.skipTest("Models not yet migrated")
    
    def test_buoy_health_status_creation(self):
        """Test BuoyHealthStatus model."""
        try:
            from security.models.ocean_entropy_models import BuoyHealthStatus
            
            status = BuoyHealthStatus.objects.create(
                buoy_id='44013',
                buoy_name='Boston Buoy',
                health_status='excellent',
                data_freshness_minutes=5,
                data_completeness=0.95,
                average_quality_score=0.92,
                uptime_percentage=98.5,
                total_readings_24h=48,
                current_wave_height=2.3,
            )
            
            self.assertEqual(status.health_status, 'excellent')
            self.assertIn('🟢', str(status))
        except ImportError:
            self.skipTest("Models not yet migrated")
    
    def test_ocean_entropy_usage_stats_creation(self):
        """Test OceanEntropyUsageStats model."""
        try:
            from security.models.ocean_entropy_models import OceanEntropyUsageStats
            
            stats = OceanEntropyUsageStats.objects.create(
                user=self.user,
                total_ocean_passwords=10,
                total_hybrid_passwords=25,
                favorite_buoy_id='44013',
                average_quality_score=0.9,
            )
            
            self.assertEqual(stats.total_ocean_passwords, 10)
            self.assertEqual(stats.favorite_buoy_id, '44013')
        except ImportError:
            self.skipTest("Models not yet migrated")


# =============================================================================
# Configuration Tests
# =============================================================================

class TestOceanEntropyConfig(TestCase):
    """Tests for ocean entropy configuration."""
    
    def test_default_config_values(self):
        """Test default configuration values."""
        from security.services.ocean_wave_entropy_service import OceanEntropyConfig
        
        self.assertTrue(OceanEntropyConfig.ENABLED)
        self.assertEqual(OceanEntropyConfig.MIN_BUOYS, 2)
        self.assertGreater(OceanEntropyConfig.MIN_ENTROPY_BITS, 0)
        self.assertEqual(OceanEntropyConfig.POOL_CONTRIBUTION_PERCENT, 25)
