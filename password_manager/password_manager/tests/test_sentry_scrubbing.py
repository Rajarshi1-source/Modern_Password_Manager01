"""
Phase E / E1 (2026-05): Sentry payload scrubber tests.

Confirms the redaction surface published by
``password_manager.sentry_scrubbing``. Each test builds a synthetic
Sentry event dict (matching the Sentry JSON schema for the relevant
section) and asserts the scrubber redacts what it should and leaves
the rest alone.

These tests do NOT require sentry-sdk to be installed — the scrubber
is a pure data transformation on a dict. They DO require Django so
the discovery hooks find them, but they don't touch the DB.
"""

from django.test import SimpleTestCase

from password_manager.sentry_scrubbing import (
    is_sensitive_key,
    scrub_event,
    scrub_mapping,
    scrub_str,
)


class IsSensitiveKeyTests(SimpleTestCase):
    """Pin the key-matching surface."""

    def test_env_var_names_match_exactly(self):
        self.assertTrue(is_sensitive_key('BLOCKCHAIN_PRIVATE_KEY'))
        self.assertTrue(is_sensitive_key('SECRET_KEY'))

    def test_pattern_substring_match(self):
        # Phase E / E1: ``TOKEN`` catches all *_token variants.
        self.assertTrue(is_sensitive_key('verification_token'))
        self.assertTrue(is_sensitive_key('id_token'))
        self.assertTrue(is_sensitive_key('csrf_token'))
        self.assertTrue(is_sensitive_key('session_token'))
        # ``VERIFICATION`` catches verification_*.
        self.assertTrue(is_sensitive_key('verification_code'))
        # Pre-existing patterns still match.
        self.assertTrue(is_sensitive_key('user_password'))
        self.assertTrue(is_sensitive_key('client_secret'))

    def test_authorization_and_cookie_keys_match(self):
        # Audit finding #5: header keys carrying credentials.
        self.assertTrue(is_sensitive_key('Authorization'))
        self.assertTrue(is_sensitive_key('authorization'))
        self.assertTrue(is_sensitive_key('Cookie'))
        self.assertTrue(is_sensitive_key('Set-Cookie'))

    def test_benign_keys_not_matched(self):
        self.assertFalse(is_sensitive_key('user_id'))
        self.assertFalse(is_sensitive_key('email'))
        self.assertFalse(is_sensitive_key('created_at'))

    def test_non_string_keys_return_false(self):
        self.assertFalse(is_sensitive_key(123))
        self.assertFalse(is_sensitive_key(None))
        self.assertFalse(is_sensitive_key(('tuple', 'key')))


class ScrubStrTests(SimpleTestCase):

    def test_redacts_eth_address(self):
        # 40-hex 0x-prefixed → redacted
        out = scrub_str('signer=0xabcdef1234567890abcdef1234567890abcdef12')
        self.assertEqual(out, 'signer=0x<redacted>')

    def test_redacts_64_hex_hash(self):
        out = scrub_str('tx=0x' + 'a' * 64)
        self.assertEqual(out, 'tx=0x<redacted>')

    def test_passthrough_normal_string(self):
        self.assertEqual(scrub_str('hello world'), 'hello world')

    def test_passthrough_short_hex(self):
        # 32-bit IDs are below the 40-char floor.
        self.assertEqual(scrub_str('id=0xdeadbeef'), 'id=0xdeadbeef')

    def test_non_string_passthrough(self):
        self.assertEqual(scrub_str(42), 42)
        self.assertIsNone(scrub_str(None))

    # Audit finding #5: JWT + bearer redaction in free-text strings.

    def test_redacts_bare_jwt(self):
        jwt = (
            'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
            '.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ'
            '.dummysignaturesegmentdQssw5c'
        )
        out = scrub_str(f'decoded token {jwt} for user')
        self.assertEqual(out, 'decoded token <redacted> for user')
        self.assertNotIn('eyJ', out)

    def test_redacts_bearer_token_keeps_prefix(self):
        out = scrub_str('Authorization: Bearer abc123.def-456_GHI')
        self.assertEqual(out, 'Authorization: Bearer <redacted>')

    def test_redacts_bearer_jwt_single_pass(self):
        jwt = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sigsegmentvalue'
        out = scrub_str(f'header=Bearer {jwt}')
        self.assertEqual(out, 'header=Bearer <redacted>')
        self.assertNotIn('eyJ', out)

    def test_bearer_case_insensitive(self):
        self.assertEqual(scrub_str('bearer opaqueToken99'), 'bearer <redacted>')

    def test_redacts_bearer_base64_token_with_special_chars(self):
        # Standard base64 (not base64url) tokens contain +, /, = — the
        # whole token must be redacted, not just the [\w.-] prefix.
        out = scrub_str('Authorization: Bearer abc+def/ghi=jkl==')
        self.assertEqual(out, 'Authorization: Bearer <redacted>')

    def test_bearer_redaction_stops_at_whitespace(self):
        # \S+ is greedy but bounded by whitespace, so trailing context
        # after the token survives.
        out = scrub_str('Bearer tok+en/value= and more text')
        self.assertEqual(out, 'Bearer <redacted> and more text')

    def test_passthrough_dotted_identifier_not_a_jwt(self):
        # Ordinary dotted names must NOT trip the JWT matcher (the
        # ``eyJ`` anchor is what keeps this safe).
        self.assertEqual(
            scrub_str('module.submodule.attr'), 'module.submodule.attr'
        )


class ScrubMappingTests(SimpleTestCase):

    def test_redacts_sensitive_keys(self):
        # Test fixture values are intentionally low-entropy so Gitleaks
        # doesn't flag them as plausible real secrets in the test file.
        # The scrubber's behaviour depends on KEY NAMES, not value
        # contents, so a dummy literal is sufficient.
        out = scrub_mapping({
            'user_id': 7,
            'password': 'dummy-password-value',  # pragma: allowlist secret
            'verification_token': 'dummy-fixture-token',  # pragma: allowlist secret
            'email': 'a@b.com',
        })
        self.assertEqual(out['user_id'], 7)
        self.assertEqual(out['email'], 'a@b.com')
        self.assertEqual(out['password'], '<redacted>')
        self.assertEqual(out['verification_token'], '<redacted>')

    def test_recurses_into_nested_dicts(self):
        out = scrub_mapping({
            'request': {
                'headers': {
                    'authorization': 'Bearer xyz',
                    'x-token': 'opaque',
                },
            },
        })
        self.assertEqual(out['request']['headers']['x-token'], '<redacted>')

    def test_recurses_into_lists(self):
        out = scrub_mapping({
            'connections': [
                {'access_token': 'a', 'name': 'svc-a'},
                {'access_token': 'b', 'name': 'svc-b'},
            ],
        })
        for entry in out['connections']:
            self.assertEqual(entry['access_token'], '<redacted>')
            self.assertIn(entry['name'], ('svc-a', 'svc-b'))

    def test_authorization_header_value_redacted_by_key(self):
        # Audit finding #5: ``Authorization`` matched no prior pattern,
        # so a Bearer token in a request-headers dict leaked through.
        out = scrub_mapping({
            'request': {
                'headers': {
                    'Authorization': 'Bearer secret.jwt.value',
                    'Cookie': 'sessionid=abc; csrftoken=def',
                    'User-Agent': 'pytest',
                },
            },
        })
        headers = out['request']['headers']
        self.assertEqual(headers['Authorization'], '<redacted>')
        self.assertEqual(headers['Cookie'], '<redacted>')
        self.assertEqual(headers['User-Agent'], 'pytest')

    def test_passthrough_non_mapping(self):
        self.assertEqual(scrub_mapping('not a dict'), 'not a dict')
        self.assertEqual(scrub_mapping(None), None)


class ScrubEventBreadcrumbsTests(SimpleTestCase):
    """Phase E / E1: the breadcrumbs scrubbing branch added this phase."""

    def test_breadcrumb_message_hex_blob_redacted(self):
        event = {
            'breadcrumbs': {
                'values': [
                    {
                        'category': 'log',
                        'level': 'info',
                        'message': 'loaded key=0x' + 'f' * 40,
                    },
                ],
            },
        }
        out = scrub_event(event)
        self.assertEqual(
            out['breadcrumbs']['values'][0]['message'],
            'loaded key=0x<redacted>',
        )

    def test_breadcrumb_data_dict_redacted(self):
        event = {
            'breadcrumbs': {
                'values': [
                    {
                        'category': 'log',
                        'data': {
                            # Low-entropy fixture — see comment in
                            # test_redacts_sensitive_keys above.
                            'verification_token': 'dummy-fixture-token',  # pragma: allowlist secret
                            'user_id': 9,
                        },
                    },
                ],
            },
        }
        out = scrub_event(event)
        crumb = out['breadcrumbs']['values'][0]
        self.assertEqual(crumb['data']['verification_token'], '<redacted>')
        self.assertEqual(crumb['data']['user_id'], 9)

    def test_breadcrumb_with_no_message_or_data_unchanged(self):
        # Some crumbs (e.g. SQL spans) only carry category/timestamp.
        event = {
            'breadcrumbs': {
                'values': [
                    {'category': 'http', 'level': 'info'},
                ],
            },
        }
        out = scrub_event(event)
        self.assertEqual(out['breadcrumbs']['values'][0]['category'], 'http')

    def test_event_without_breadcrumbs_does_not_raise(self):
        event = {'message': 'ok'}
        out = scrub_event(event)
        self.assertEqual(out['message'], 'ok')


class ScrubEventFrameLocalsTests(SimpleTestCase):
    """Phase E / E1: verification_token now caught by TOKEN pattern."""

    def test_frame_var_verification_token_redacted(self):
        event = {
            'exception': {
                'values': [{
                    'stacktrace': {
                        'frames': [{
                            'function': 'notify_beneficiary',
                            'vars': {
                                'beneficiary_id': 7,
                                # Low-entropy fixture — see comment in
                                # test_redacts_sensitive_keys above.
                                'verification_token': 'dummy-fixture-token',  # pragma: allowlist secret
                                'message': 'Email body with the token in it',
                            },
                        }],
                    },
                }],
            },
        }
        out = scrub_event(event)
        frame_vars = out['exception']['values'][0]['stacktrace']['frames'][0]['vars']
        self.assertEqual(frame_vars['verification_token'], '<redacted>')
        self.assertEqual(frame_vars['beneficiary_id'], 7)


class ScrubEventNeverRaisesTests(SimpleTestCase):
    """The contract: ``before_send`` MUST NOT raise — losing telemetry
    is preferable to crashing the application's exception path."""

    def test_malformed_event_returns_event_as_is(self):
        # ``exception`` is supposed to be a dict; passing a string
        # should not raise.
        event = {'exception': 'not-a-dict'}
        out = scrub_event(event)
        self.assertEqual(out, {'exception': 'not-a-dict'})

    def test_nested_typeerror_swallowed(self):
        # ``logentry.params`` should be dict/list/tuple — passing an
        # int forces the codepath that would TypeError on iteration.
        event = {'logentry': {'message': 'x', 'params': 12345}}
        out = scrub_event(event)
        self.assertEqual(out['logentry']['message'], 'x')
