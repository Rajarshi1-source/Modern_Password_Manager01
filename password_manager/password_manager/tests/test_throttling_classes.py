"""
Phase G / G1 (2026-05): regression tests for the throttling-class
parent classes.

Background: DRF's ``ScopedRateThrottle.allow_request`` reads the
scope from the view's ``throttle_scope`` attribute, not from the
throttle class. No view in this codebase sets ``throttle_scope``,
so every previously-``ScopedRateThrottle`` subclass that declared a
class-level ``scope = '...'`` was silently disabled — DRF reset
``self.scope`` to None on every call and allow_request short-circuited
to True.

Phase G migrated those classes to ``SimpleRateThrottle``, which reads
``self.scope`` directly from the class and populates the rate /
num_requests / duration from settings. The tests below pin the new
shape so the regression can't return — a future refactor that
accidentally puts ``ScopedRateThrottle`` back in the parent list will
fail here loudly.
"""

import inspect

from rest_framework.throttling import (
    ScopedRateThrottle,
    SimpleRateThrottle,
)

from django.test import SimpleTestCase

from password_manager import throttling as throttling_module
from password_manager.throttling import (
    AuthRateThrottle,
    PasswordCheckRateThrottle,
    SecurityOperationThrottle,
    PasskeyThrottle,
    WhatIfSimulationThrottle,
    DeadDropCollectThrottle,
    MeshNodePingThrottle,
    HoneypotWebhookThrottle,
)


# Every throttle class whose ``scope`` attribute drives a real
# per-request limit. Each one MUST be a ``SimpleRateThrottle`` and
# MUST NOT be a ``ScopedRateThrottle``.
_THROTTLES_WITH_SCOPE = [
    AuthRateThrottle,
    PasswordCheckRateThrottle,
    SecurityOperationThrottle,
    PasskeyThrottle,
    WhatIfSimulationThrottle,
    DeadDropCollectThrottle,
    MeshNodePingThrottle,
    HoneypotWebhookThrottle,
]


class ThrottleParentClassRegressionTests(SimpleTestCase):
    """Pin the SimpleRateThrottle vs ScopedRateThrottle invariant."""

    def test_no_module_class_subclasses_scoped_rate_throttle(self):
        """PR #278 review (CodeRabbit): belt-and-suspenders module-wide
        scan. The hand-maintained ``_THROTTLES_WITH_SCOPE`` list above
        could miss a future class added directly to
        ``password_manager.throttling`` — this test fails if ANY class
        defined in that module (not imported from elsewhere) is a
        subclass of ``ScopedRateThrottle``. Closes the "forgotten to
        add to the list" gap that a hand-maintained allowlist always
        has.
        """
        scoped_subclasses = [
            cls.__name__
            for _, cls in inspect.getmembers(throttling_module, inspect.isclass)
            # Restrict to classes DEFINED in the throttling module,
            # not re-imported from DRF — we don't care that
            # ``rest_framework.throttling.ScopedRateThrottle`` itself
            # is in scope, just that this codebase doesn't subclass it.
            if cls.__module__ == throttling_module.__name__
            and cls is not ScopedRateThrottle
            and issubclass(cls, ScopedRateThrottle)
        ]
        self.assertEqual(
            scoped_subclasses, [],
            msg=(
                "password_manager.throttling defines ScopedRateThrottle "
                f"subclass(es): {scoped_subclasses!r}. These will be "
                "silently disabled at runtime because no view in this "
                "codebase sets ``throttle_scope``. Switch the parent "
                "to ``SimpleRateThrottle`` (and add the class to "
                "_THROTTLES_WITH_SCOPE below so it gets the rate/scope "
                "checks too)."
            ),
        )

    def test_none_subclass_scoped_rate_throttle(self):
        """The regression we're guarding against: putting any of
        these classes back under ``ScopedRateThrottle`` silently
        disables them, because no view sets ``throttle_scope``."""
        for cls in _THROTTLES_WITH_SCOPE:
            with self.subTest(throttle=cls.__name__):
                self.assertFalse(
                    issubclass(cls, ScopedRateThrottle),
                    msg=(
                        f"{cls.__name__} extends ScopedRateThrottle. "
                        f"This silently disables the throttle because "
                        f"no view in this codebase sets throttle_scope. "
                        f"See module docstring at "
                        f"password_manager/throttling.py for context."
                    ),
                )
                self.assertTrue(
                    issubclass(cls, SimpleRateThrottle),
                    msg=(
                        f"{cls.__name__} must extend SimpleRateThrottle "
                        f"so the class-level ``scope`` attribute is "
                        f"actually honoured."
                    ),
                )

    def test_all_load_a_rate_from_settings(self):
        """Each throttle's scope must have a matching entry in
        ``DEFAULT_THROTTLE_RATES``. SimpleRateThrottle reads it in
        __init__ and would raise ImproperlyConfigured if missing."""
        for cls in _THROTTLES_WITH_SCOPE:
            with self.subTest(throttle=cls.__name__):
                t = cls()
                self.assertIsNotNone(
                    t.num_requests,
                    msg=f"{cls.__name__} num_requests is None — "
                        f"scope {t.scope!r} likely missing from "
                        f"REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].",
                )
                self.assertGreater(t.num_requests, 0)
                self.assertGreater(t.duration, 0)

    def test_each_class_has_a_distinct_scope(self):
        """No two of these throttles should share a scope — they would
        eat from the same bucket, which is never what we want."""
        scopes = [cls.scope for cls in _THROTTLES_WITH_SCOPE]
        self.assertEqual(
            len(scopes), len(set(scopes)),
            msg=f"Duplicate scopes across throttle classes: {scopes!r}",
        )
