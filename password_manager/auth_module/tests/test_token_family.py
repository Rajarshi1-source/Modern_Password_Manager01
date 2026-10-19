"""
auth_module.token_family: the per-user refresh-token cap.

Concurrent logins used to count and blacklist without a lock, so two
requests could pick the same "oldest" tokens and one get_or_create failed
with an IntegrityError (logged). Enforcement is now one locked transaction
with a single bulk insert.
"""
from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
import threading

from django.db import connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from auth_module.token_family import (
    FamilyLimitedTokenObtainPairSerializer,
    aenforce_token_family_limit,
    enforce_token_family_limit,
)


def live_ids(user):
    """The user's non-blacklisted outstanding token ids, oldest first."""
    return list(
        OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True)
        .order_by('created_at', 'id').values_list('id', flat=True)
    )


@override_settings(SIMPLE_JWT={'REFRESH_TOKEN_FAMILY_MAX_SIZE': 3})
class TokenFamilyLimitTests(TestCase):
    """Enforcement logic on one connection (the lock itself: see below)."""

    def setUp(self):
        self.user = User.objects.create_user('family', 'family@example.com', 'Family-Pass-1!')

    def _issue(self, n):
        """Mint ``n`` refresh tokens (each records an OutstandingToken)."""
        for _ in range(n):
            RefreshToken.for_user(self.user)

    def test_oldest_tokens_beyond_the_cap_are_blacklisted(self):
        """Exactly the oldest excess tokens are blacklisted, in one pass."""
        self._issue(5)
        before = live_ids(self.user)
        self.assertEqual(enforce_token_family_limit(self.user), 2)
        self.assertEqual(live_ids(self.user), before[2:])
        self.assertEqual(
            set(BlacklistedToken.objects.values_list('token_id', flat=True)), set(before[:2]),
        )

    def test_under_the_cap_is_a_no_op(self):
        """At the cap nothing is blacklisted."""
        self._issue(3)
        self.assertEqual(enforce_token_family_limit(self.user), 0)
        self.assertFalse(BlacklistedToken.objects.exists())

    def test_running_twice_does_not_fail_or_blacklist_more(self):
        """A second pass is a no-op rather than an IntegrityError."""
        # The second pass sees the first pass's blacklist (what concurrent
        # logins now do under the row lock) and has nothing to do.
        self._issue(5)
        enforce_token_family_limit(self.user)
        self.assertEqual(enforce_token_family_limit(self.user), 0)
        self.assertEqual(len(live_ids(self.user)), 3)

    def test_already_blacklisted_tokens_are_not_counted(self):
        """Tokens revoked elsewhere (logout) do not count toward the cap."""
        self._issue(4)
        BlacklistedToken.objects.create(token_id=live_ids(self.user)[-1])
        self.assertEqual(enforce_token_family_limit(self.user), 0)

    def test_other_users_tokens_are_untouched(self):
        """The cap is per user."""
        other = User.objects.create_user('other', 'other@example.com', 'Other-Pass-1!')
        for _ in range(5):
            RefreshToken.for_user(other)
        self._issue(4)
        enforce_token_family_limit(self.user)
        self.assertEqual(len(live_ids(other)), 5)

    def test_async_entry_point(self):
        """The async wrapper enforces the same cap."""
        self._issue(4)
        self.assertEqual(async_to_sync(aenforce_token_family_limit)(self.user), 1)
        self.assertEqual(len(live_ids(self.user)), 3)

    def test_login_serializer_enforces_the_cap(self):
        """Logging in through the serializer keeps the family at the cap."""
        self._issue(3)
        serializer = FamilyLimitedTokenObtainPairSerializer(
            data={'username': 'family', 'password': 'Family-Pass-1!'}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(len(live_ids(self.user)), 3)


@override_settings(SIMPLE_JWT={'REFRESH_TOKEN_FAMILY_MAX_SIZE': 3})
class TokenFamilyLockTests(TransactionTestCase):
    """The user-row lock, with a second real connection.

    ``TokenFamilyLimitTests`` runs on one connection, where a lock never
    blocks, so it cannot tell a missing ``select_for_update()`` from a
    working one. Here a concurrent login holds the lock mid-enforcement and
    the call under test must wait for it and then see its commit.
    """

    def setUp(self):
        """A user already at the cap plus one."""
        self.user = User.objects.create_user('locked', 'locked@example.com', 'Locked-Pass-1!')
        for _ in range(4):
            RefreshToken.for_user(self.user)

    def test_enforcement_waits_for_a_concurrent_login_and_sees_its_commit(self):
        """Without the lock this pass reads the pre-commit family (4 live
        tokens) and blacklists a token the other login already handled,
        returning 1; with it, it waits, sees 3 live tokens and returns 0."""
        if connection.vendor == 'sqlite':
            self.skipTest(
                "select_for_update() row-locking needs real MVCC. SQLite "
                "serializes writers at the file level instead. Runs against "
                "Postgres in CI."
            )

        has_lock = threading.Event()
        may_commit = threading.Event()
        errors = []

        def concurrent_login():
            """Mint a token and blacklist the two oldest under the lock,
            committing only once the main thread's call has been issued."""
            try:
                with transaction.atomic():
                    User.objects.select_for_update().filter(pk=self.user.pk).exists()
                    oldest = live_ids(self.user)[:2]
                    RefreshToken.for_user(self.user)
                    has_lock.set()
                    if not may_commit.wait(timeout=5):
                        raise RuntimeError('main thread never started enforcement')
                    BlacklistedToken.objects.bulk_create(
                        [BlacklistedToken(token_id=token_id) for token_id in oldest]
                    )
            except Exception as exc:  # noqa: BLE001 - surfaced below
                errors.append(exc)
            finally:
                connections.close_all()

        login = threading.Thread(target=concurrent_login)
        login.start()
        self.assertTrue(has_lock.wait(timeout=5), 'concurrent login never took the lock')
        # Release the other login only after this call has started, so the
        # call's lock acquisition genuinely has to wait.
        threading.Timer(0.3, may_commit.set).start()

        blacklisted = enforce_token_family_limit(self.user)
        login.join(timeout=10)

        self.assertFalse(login.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(blacklisted, 0)
        self.assertEqual(len(live_ids(self.user)), 3)
        self.assertEqual(BlacklistedToken.objects.count(), 2)
