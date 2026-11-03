"""Replacing the vault key after a recovery compromise (VaultKeyReplaceView) and
moving rows off a replaced key (VaultStaleItemsView). The server only stores and
compares ciphertext, so the values here are placeholders of the right shape; the
browser side is in sessionVaultCryptoV3.replaceKey.test.js."""
import base64
import json
import uuid

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient

from auth_module.models import LoginVerifierState
from auth_module.recovery_models_v2 import RecoveryWrappedDEK, VaultWrappedDEK
from auth_module.recovery_notice import acknowledge_exposure, create_notice
from auth_module.time_locked_models import TimeLockedRecovery
from vault.models.vault_models import EncryptedVaultItem

REPLACE_URL = '/api/auth/vault/wrapped-dek/replace-key/'
STALE_URL = '/api/auth/vault/wrapped-dek/stale-items/'
WRAPPED_URL = '/api/auth/vault/wrapped-dek/'
VERIFIER = base64.b64encode(b'v' * 32).decode()
OLD_BLOB = {'v': 'wdek-1', 'kdf': 'argon2id', 'kdf_params': {}, 'salt': 'old', 'iv': 'old', 'wrapped': 'old'}
NEW_BLOB = {**OLD_BLOB, 'salt': 'new', 'iv': 'new', 'wrapped': 'new'}


def envelope(dek_id):
    return json.dumps({'v': 'svc-gcm-2', 'iv': 'aXY=', 'ct': 'Y3Q=', 'dek_id': str(dek_id)},
                      separators=(',', ':'))


def retired(dek_id):
    return {'v': 'rdek-1', 'dek_id': str(dek_id), 'iv': 'aXY=', 'wrapped': 'd3JhcHBlZA=='}


@pytest.fixture(autouse=True)
def clear_throttles():
    cache.clear()


@pytest.fixture
def user(db):
    return User.objects.create_user(username='alice', password=VERIFIER)


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture
def wrapped(user):
    return VaultWrappedDEK.objects.create(user=user, blob=OLD_BLOB)


@pytest.fixture
def exposed(user):
    return create_notice(user, 'account_unlocked', send_email=False)


def body(row, **overrides):
    return {'dek_id': str(row.dek_id), 'blob': NEW_BLOB, 'retired_key': retired(row.dek_id),
            'login_verifier': VERIFIER, **overrides}


@pytest.mark.django_db
class TestReplaceKey:
    def test_swaps_the_key_and_keeps_the_old_one_sealed(self, client, wrapped, exposed):
        old_id = wrapped.dek_id
        r = client.post(REPLACE_URL, body(wrapped), format='json')
        assert r.status_code == 200
        wrapped.refresh_from_db()
        assert wrapped.dek_id != old_id
        assert str(wrapped.dek_id) == r.json()['dek_id']
        assert wrapped.blob == NEW_BLOB
        assert wrapped.retired_keys == [retired(old_id)]
        assert wrapped.key_replaced_at is not None

    def test_revokes_factors_and_time_lock_and_ends_sessions(self, client, user, wrapped, exposed):
        factor = RecoveryWrappedDEK.objects.create(
            user=user, factor_type='recovery_key', dek_id=wrapped.dek_id, blob=OLD_BLOB)
        half = TimeLockedRecovery.objects.create(user=user, server_half=b'x', is_active=True)
        assert client.post(REPLACE_URL, body(wrapped), format='json').status_code == 200
        factor.refresh_from_db()
        half.refresh_from_db()
        assert factor.status == RecoveryWrappedDEK.Status.REVOKED
        assert half.is_active is False
        assert LoginVerifierState.objects.get(user=user).sessions_revoked_at is not None

    def test_a_later_read_returns_the_chain(self, client, wrapped, exposed):
        old_id = wrapped.dek_id
        client.post(REPLACE_URL, body(wrapped), format='json')
        cache.clear()
        assert client.get(WRAPPED_URL).json()['retired_keys'] == [retired(old_id)]

    def test_refused_without_an_open_exposure_warning(self, client, user, wrapped):
        # Before support's unlock, whoever completed the recovery may hold the
        # master password, and this would cut the owner's factors off for good.
        assert client.post(REPLACE_URL, body(wrapped), format='json').status_code == 403
        wrapped.refresh_from_db()
        assert wrapped.blob == OLD_BLOB

    def test_refused_after_the_warning_is_acknowledged(self, client, user, wrapped, exposed):
        acknowledge_exposure(user)
        assert client.post(REPLACE_URL, body(wrapped), format='json').status_code == 403

    def test_refused_twice_for_one_exposure(self, client, wrapped, exposed):
        assert client.post(REPLACE_URL, body(wrapped), format='json').status_code == 200
        wrapped.refresh_from_db()
        cache.clear()
        assert client.post(REPLACE_URL, body(wrapped), format='json').status_code == 409

    def test_a_stolen_session_alone_cannot_do_it(self, client, wrapped, exposed):
        wrong = base64.b64encode(b'w' * 32).decode()
        r = client.post(REPLACE_URL, body(wrapped, login_verifier=wrong), format='json')
        assert r.status_code == 403
        wrapped.refresh_from_db()
        assert wrapped.blob == OLD_BLOB

    def test_needs_the_current_dek_id(self, client, wrapped, exposed):
        r = client.post(REPLACE_URL, body(wrapped, dek_id=str(uuid.uuid4())), format='json')
        assert r.status_code == 409

    @pytest.mark.parametrize('bad', [
        None, {}, {'v': 'rdek-1'}, {'v': 'x', 'dek_id': 'x', 'iv': 'a', 'wrapped': 'b'},
    ])
    def test_rejects_a_malformed_retired_key(self, client, wrapped, exposed, bad):
        # Losing the old key here would leave its rows unreadable.
        r = client.post(REPLACE_URL, body(wrapped, retired_key=bad), format='json')
        assert r.status_code == 400
        wrapped.refresh_from_db()
        assert wrapped.retired_keys == []

    def test_rejects_a_retired_key_for_another_id(self, client, wrapped, exposed):
        r = client.post(REPLACE_URL, body(wrapped, retired_key=retired(uuid.uuid4())), format='json')
        assert r.status_code == 400

    def test_requires_authentication(self, wrapped):
        assert APIClient().post(REPLACE_URL, {}, format='json').status_code in (401, 403)

    def test_the_notices_report_the_replacement(self, client, wrapped, exposed):
        client.post(REPLACE_URL, body(wrapped), format='json')
        data = client.get('/api/auth/recovery-notices/').json()
        assert data['vault_key_replaced_at'] is not None
        assert data['username'] == 'alice'


@pytest.mark.django_db
class TestStaleItems:
    def item(self, user, encrypted_data, **fields):
        return EncryptedVaultItem.objects.create(
            user=user, item_type='password', encrypted_data=encrypted_data, **fields)

    def test_lists_only_rows_under_another_v3_key(self, client, user, wrapped):
        stale = self.item(user, envelope(uuid.uuid4()))
        trashed = self.item(user, envelope(uuid.uuid4()), deleted=True)
        self.item(user, envelope(wrapped.dek_id))
        self.item(user, json.dumps({'v': 'svc-gcm-1', 'iv': 'a', 'ct': 'b', 'salt': 'c'}))
        items = client.get(STALE_URL).json()['items']
        assert {i['id'] for i in items} == {str(stale.id), str(trashed.id)}

    def test_does_not_list_another_users_rows(self, client, wrapped, db):
        other = User.objects.create_user(username='bob', password='x')
        self.item(other, envelope(uuid.uuid4()))
        assert client.get(STALE_URL).json()['items'] == []

    def test_pages_past_rows_the_browser_cannot_read(self, client, user, wrapped):
        for _ in range(51):
            self.item(user, envelope(uuid.uuid4()))
        first = client.get(STALE_URL).json()
        assert len(first['items']) == 50 and first['next']
        second = client.get(STALE_URL, {'after': first['next']}).json()
        assert len(second['items']) == 1 and second['next'] is None

    def test_rewrites_a_row_and_keeps_its_timestamp(self, client, user, wrapped):
        row = self.item(user, envelope(uuid.uuid4()))
        listed = client.get(STALE_URL).json()['items'][0]
        new = envelope(wrapped.dek_id)
        r = client.post(STALE_URL, {'items': [{**listed, 'encrypted_data': new}]}, format='json')
        assert r.json() == {'rewritten': 1}
        before = row.updated_at
        row.refresh_from_db()
        assert row.encrypted_data == new
        assert row.updated_at == before

    def test_leaves_a_row_edited_since_it_was_read(self, client, user, wrapped):
        row = self.item(user, envelope(uuid.uuid4()))
        listed = client.get(STALE_URL).json()['items'][0]
        row.encrypted_data = envelope(wrapped.dek_id)
        row.save()
        edited = row.encrypted_data
        r = client.post(STALE_URL, {'items': [{**listed, 'encrypted_data': envelope(wrapped.dek_id)}]},
                        format='json')
        assert r.json() == {'rewritten': 0}
        row.refresh_from_db()
        assert row.encrypted_data == edited

    def test_refuses_to_seal_a_row_under_an_old_key(self, client, user, wrapped):
        self.item(user, envelope(uuid.uuid4()))
        listed = client.get(STALE_URL).json()['items'][0]
        r = client.post(STALE_URL, {'items': [{**listed, 'encrypted_data': envelope(uuid.uuid4())}]},
                        format='json')
        assert r.status_code == 400

    def test_cannot_write_another_users_row(self, client, wrapped, db):
        other = User.objects.create_user(username='bob', password='x')
        row = self.item(other, envelope(uuid.uuid4()))
        original = row.encrypted_data
        r = client.post(STALE_URL, {'items': [{
            'id': str(row.id), 'updated_at': row.updated_at.isoformat(),
            'encrypted_data': envelope(wrapped.dek_id),
        }]}, format='json')
        assert r.json() == {'rewritten': 0}
        row.refresh_from_db()
        assert row.encrypted_data == original

    def test_rejects_too_many_rows_at_once(self, client, wrapped):
        r = client.post(STALE_URL, {'items': [{}] * 51}, format='json')
        assert r.status_code == 400
