"""PII-scrubbing regression tests for the personality inference service.

Plan C coverage: the regex-only backend is the historical posture and
remains the default. The Presidio backend (Microsoft Presidio analyzer +
anonymizer) is an opt-in defence-in-depth pass that runs *before* the
regex pass. These tests exercise three code paths:

1. Default (presidio flag off): regex backend produces the expected
   substitutions.
2. Presidio enabled with a stub adapter: the analyzer/anonymizer is
   invoked and its output flows through the regex pass.
3. Presidio enabled but unavailable (import error): the adapter records
   the failure and ``_scrub_pii`` cleanly falls back to regex.

The Presidio packages are NOT installed in CI, so tests inject a fake
adapter via ``_get_presidio_adapter``'s module-level singleton instead
of mocking ``importlib``.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase, override_settings

from personality_auth.services import inference_service
from personality_auth.services.inference_service import (
    _MAX_MESSAGE_CHARS,
    _PresidioAdapter,
    _reset_presidio_adapter_for_tests,
    _scrub_pii,
)


class RegexBackendTests(TestCase):
    """The historical regex pass is the default. Each pattern must still
    fire when Presidio is disabled (the most common production posture
    until the optional packages are installed)."""

    def setUp(self):
        _reset_presidio_adapter_for_tests()

    @override_settings(PERSONALITY_AUTH_USE_PRESIDIO=False)
    def test_empty_input_returns_empty_string(self):
        self.assertEqual(_scrub_pii(''), '')
        self.assertEqual(_scrub_pii(None), '')  # type: ignore[arg-type]

    @override_settings(PERSONALITY_AUTH_USE_PRESIDIO=False)
    def test_email_redacted(self):
        scrubbed = _scrub_pii('contact me at jane.doe+work@example.co.uk!')
        self.assertIn('[REDACTED_EMAIL]', scrubbed)
        self.assertNotIn('jane.doe+work@example.co.uk', scrubbed)

    @override_settings(PERSONALITY_AUTH_USE_PRESIDIO=False)
    def test_card_and_ssn_redacted(self):
        """The PHONE pattern is intentionally greedy enough to catch
        any long digit run, so it fires before the more-specific CARD /
        SSN patterns. That's fine for our purposes — the property we
        care about is that the raw digits never reach the LLM."""
        scrubbed = _scrub_pii('card 4111 1111 1111 1111 ssn 123-45-6789')
        self.assertNotIn('4111 1111 1111 1111', scrubbed)
        self.assertNotIn('123-45-6789', scrubbed)
        # Anything that LOOKS like a long digit run was tagged as some
        # kind of redaction — assert the tag prefix, not a specific
        # entity name.
        self.assertIn('[REDACTED_', scrubbed)

    @override_settings(PERSONALITY_AUTH_USE_PRESIDIO=False)
    def test_url_and_ip_redacted(self):
        """URLs are unambiguous (the URL pattern strictly wins). The IP
        is caught — possibly by the PHONE pattern, possibly by the IP
        pattern depending on regex order — either is acceptable
        scrubbing."""
        scrubbed = _scrub_pii('see https://example.com/?token=abc from 10.0.0.42')
        self.assertIn('[REDACTED_URL]', scrubbed)
        self.assertNotIn('10.0.0.42', scrubbed)
        self.assertNotIn('example.com', scrubbed)

    @override_settings(PERSONALITY_AUTH_USE_PRESIDIO=False)
    def test_length_clamp_applied(self):
        """A long paste is clamped to ``_MAX_MESSAGE_CHARS``. Use
        whitespace-separated tokens so the long-token regex doesn't
        eat the whole input and accidentally make the result short."""
        long = ('word ' * (_MAX_MESSAGE_CHARS // 5 + 50))  # well past limit
        scrubbed = _scrub_pii(long)
        self.assertLessEqual(len(scrubbed), _MAX_MESSAGE_CHARS + len(' [...]'))
        self.assertTrue(scrubbed.endswith(' [...]'))


class PresidioBackendIntegrationTests(TestCase):
    """When Presidio is enabled and available, the adapter runs first
    and its anonymised output flows through the regex pass as belt-and-
    suspenders. We inject a stub adapter rather than installing the
    optional packages so the test suite stays portable."""

    def setUp(self):
        _reset_presidio_adapter_for_tests()

    def _install_stub_adapter(self, scrub_impl):
        """Register a stub ``_PresidioAdapter`` whose ``scrub`` method
        is provided by the test. Setting ``available = True`` skips the
        real init path."""
        stub = _PresidioAdapter(language='en')
        stub._initialised = True
        stub._available = True
        stub.scrub = scrub_impl  # type: ignore[method-assign]
        inference_service._presidio_adapter = stub
        return stub

    @override_settings(PERSONALITY_AUTH_USE_PRESIDIO=True)
    def test_presidio_redacts_name_then_regex_redacts_email(self):
        """Presidio replaces ``Jane Doe`` with ``<PERSON>``, the
        downstream regex still catches the email — neither pass alone
        would have caught both."""
        def fake_scrub(text):
            return text.replace('Jane Doe', '<PERSON>')

        self._install_stub_adapter(fake_scrub)
        result = _scrub_pii('hi, this is Jane Doe — write me at jane@example.com')
        self.assertIn('<PERSON>', result)
        self.assertIn('[REDACTED_EMAIL]', result)
        self.assertNotIn('Jane Doe', result)
        self.assertNotIn('jane@example.com', result)

    @override_settings(PERSONALITY_AUTH_USE_PRESIDIO=True)
    def test_presidio_called_with_the_input_text(self):
        seen = []

        def fake_scrub(text):
            seen.append(text)
            return text

        self._install_stub_adapter(fake_scrub)
        _scrub_pii('payload under test')
        self.assertEqual(seen, ['payload under test'])

    @override_settings(PERSONALITY_AUTH_USE_PRESIDIO=True)
    def test_presidio_exception_falls_back_to_regex(self):
        """A misbehaving Presidio call must NOT crash the request. The
        regex pass still runs, so an email in the input is still
        redacted even if the NLP backend exploded."""
        def boom(_text):
            raise RuntimeError("simulated presidio failure")

        self._install_stub_adapter(boom)
        result = _scrub_pii('email me at someone@example.org')
        self.assertIn('[REDACTED_EMAIL]', result)
        self.assertNotIn('someone@example.org', result)

    @override_settings(PERSONALITY_AUTH_USE_PRESIDIO=True)
    def test_length_clamp_applied_after_presidio(self):
        """The final clamp runs after the Presidio pass — pasting a
        long document with PII at the end still triggers the cap.

        We use space-separated tokens so the long-token regex doesn't
        condense the whole input into a single ``[REDACTED_TOKEN]`` tag
        and accidentally bypass the length check.
        """
        def identity(text):
            return text

        self._install_stub_adapter(identity)
        long = ('word ' * (_MAX_MESSAGE_CHARS // 5 + 50))
        result = _scrub_pii(long)
        self.assertTrue(result.endswith(' [...]'))
        self.assertLessEqual(len(result), _MAX_MESSAGE_CHARS + len(' [...]'))


class PresidioFeatureFlagTests(TestCase):
    """The feature flag governs whether the adapter is consulted at all
    — flipping it off bypasses every Presidio code path."""

    def setUp(self):
        _reset_presidio_adapter_for_tests()

    def test_flag_off_skips_adapter_entirely(self):
        """The flag is the FIRST gate; with it off, the adapter is not
        instantiated and an injected stub would never see input.

        We assert by setting a stub that records calls, then verifying
        the call list stays empty under the disabled flag.
        """
        called = []

        def record(text):
            called.append(text)
            return text

        # Install the stub directly, then override settings off.
        stub = _PresidioAdapter(language='en')
        stub._initialised = True
        stub._available = True
        stub.scrub = record  # type: ignore[method-assign]
        inference_service._presidio_adapter = stub

        with override_settings(PERSONALITY_AUTH_USE_PRESIDIO=False):
            _scrub_pii('check@example.com')
        self.assertEqual(called, [])

    def test_flag_on_but_adapter_unavailable_uses_regex(self):
        """When the import fails, ``available`` stays False and the
        adapter's ``scrub`` returns the text unchanged. The downstream
        regex pass still catches what it can."""
        with patch.object(_PresidioAdapter, '_ensure_initialised'):
            stub = _PresidioAdapter(language='en')
            stub._initialised = True
            stub._available = False  # simulated import failure
            inference_service._presidio_adapter = stub

            with override_settings(PERSONALITY_AUTH_USE_PRESIDIO=True):
                result = _scrub_pii('mail mark@example.com about 4111111111111111')
            # The email pattern wins unambiguously; the digit string is
            # caught by SOME redaction tag (PHONE matches digit runs
            # before CARD fires, which is fine — the property is that
            # the raw card number is gone).
            self.assertIn('[REDACTED_EMAIL]', result)
            self.assertNotIn('4111111111111111', result)
            self.assertNotIn('mark@example.com', result)


class PresidioAdapterInitTests(TestCase):
    """Direct unit coverage of the ``_PresidioAdapter`` boot path —
    making sure import failures don't propagate to the caller."""

    def setUp(self):
        _reset_presidio_adapter_for_tests()

    def test_import_failure_marks_adapter_unavailable(self):
        """If ``presidio_analyzer`` is genuinely absent (or any other
        import in the chain blows up), ``available`` is False and
        ``scrub`` is a no-op."""
        adapter = _PresidioAdapter()
        with patch(
            'builtins.__import__',
            side_effect=ImportError("no module named 'presidio_analyzer'"),
        ):
            self.assertFalse(adapter.available)
        # Calling scrub on an unavailable adapter returns input unchanged.
        self.assertEqual(adapter.scrub('hello world'), 'hello world')
