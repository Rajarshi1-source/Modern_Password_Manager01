"""
auth_module.token_family: the per-user refresh-token cap.

Concurrent logins used to count and blacklist without a lock, so two
requests could pick the same "oldest" tokens and one get_or_create failed
with an IntegrityError (logged). Enforcement is now one locked transaction
with a single bulk insert.
"""
from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from auth_module.token_family import (
    FamilyLimitedTokenObtainPairSerializer,
    aenforce_token_family_limit,
    enforce_token_family_limit,
)


def live_ids(user):
    return list(
        OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True)
        .order_by('created_at', 'id').values_list('id', flat=True)
    )


@override_settings(SIMPLE_JWT={'REFRESH_TOKEN_FAMILY_MAX_SIZE': 3})
class TokenFamilyLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('family', 'family@example.com', 'Family-Pass-1!')

    def _issue(self, n):
        for _ in range(n):
            RefreshToken.for_user(self.user)

    def test_oldest_tokens_beyond_the_cap_are_blacklisted(self):
        self._issue(5)
        before = live_ids(self.user)
        self.assertEqual(enforce_token_family_limit(self.user), 2)
        self.assertEqual(live_ids(self.user), before[2:])
        self.assertEqual(
            set(BlacklistedToken.objects.values_list('token_id', flat=True)), set(before[:2]),
        )

    def test_under_the_cap_is_a_no_op(self):
        self._issue(3)
        self.assertEqual(enforce_token_family_limit(self.user), 0)
        self.assertFalse(BlacklistedToken.objects.exists())

    def test_running_twice_does_not_fail_or_blacklist_more(self):
        # The second pass sees the first pass's blacklist (what concurrent
        # logins now do under the row lock) and has nothing to do.
        self._issue(5)
        enforce_token_family_limit(self.user)
        self.assertEqual(enforce_token_family_limit(self.user), 0)
        self.assertEqual(len(live_ids(self.user)), 3)

    def test_already_blacklisted_tokens_are_not_counted(self):
        self._issue(4)
        BlacklistedToken.objects.create(token_id=live_ids(self.user)[-1])
        self.assertEqual(enforce_token_family_limit(self.user), 0)

    def test_other_users_tokens_are_untouched(self):
        other = User.objects.create_user('other', 'other@example.com', 'Other-Pass-1!')
        for _ in range(5):
            RefreshToken.for_user(other)
        self._issue(4)
        enforce_token_family_limit(self.user)
        self.assertEqual(len(live_ids(other)), 5)

    def test_async_entry_point(self):
        self._issue(4)
        self.assertEqual(async_to_sync(aenforce_token_family_limit)(self.user), 1)
        self.assertEqual(len(live_ids(self.user)), 3)

    def test_login_serializer_enforces_the_cap(self):
        self._issue(3)
        serializer = FamilyLimitedTokenObtainPairSerializer(
            data={'username': 'family', 'password': 'Family-Pass-1!'}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(len(live_ids(self.user)), 3)
