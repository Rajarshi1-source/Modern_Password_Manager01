"""
The FHE API must never claim FHE for a plaintext result.

concrete-python is not installed in the shipped image (every release pins
numpy<2), and TenSEAL is not in requirements-core/ml either, so in production
every FHE operation runs as plaintext. These tests pin that the services,
router and endpoints say so: availability is the live fact, `fhe_used` is
True only for results actually computed under FHE, and plaintext fallbacks
carry no fake "ciphertext".
"""

import inspect
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from fhe_service.models import FHEOperationLog
from fhe_service.services import concrete_service as cs
from fhe_service.services.concrete_service import ConcreteService, EncryptedValue
from fhe_service.services.fhe_router import (
    ComputationalBudget, EncryptionTier, FHEOperationRouter,
)
from fhe_service.services.seal_service import SEALCiphertext

PASSWORD = 'Tr0ub4dor' + '&3'


def _unavailable(name):
    svc = MagicMock(name=name)
    svc.is_available = False
    svc.get_status.return_value = {'available': False}
    return svc


@pytest.fixture
def no_concrete():
    with patch.object(cs, 'CONCRETE_AVAILABLE', False):
        yield ConcreteService()


@pytest.fixture
def plaintext_router(no_concrete):
    return FHEOperationRouter(concrete_service=no_concrete,
                              seal_service=_unavailable('seal'))


# --------------------------------------------------------------------------
# ConcreteService
# --------------------------------------------------------------------------

def test_concrete_unavailable_without_library(no_concrete):
    assert no_concrete.is_available is False
    assert no_concrete.unavailable_reason == 'concrete-python is not installed'
    status = no_concrete.get_status()
    assert status['available'] is False
    assert status['missing_circuits'] == list(cs.STANDARD_CIRCUITS)


def test_concrete_fallback_is_labelled_plaintext(no_concrete):
    enc, score = no_concrete.evaluate_strength_circuit(12, 3, False)
    assert enc.metadata['fhe'] is False
    # No fake ciphertext (it used to be a SHA-256 of the plaintext).
    assert enc.ciphertext is None
    assert enc.circuit_hash == 'plaintext'
    assert score == 70


def test_concrete_partial_compile_is_not_available():
    """Installed but a circuit failed to compile (the measured 2.11 install
    compiled 0 circuits) must NOT report available."""
    def compiled(name):
        def _compile(self):
            self._compiled_circuits[name] = object()
        return _compile

    with patch.object(cs, 'CONCRETE_AVAILABLE', True), \
            patch.object(cs, 'Configuration', MagicMock(), create=True), \
            patch.object(ConcreteService, '_compile_length_comparison_circuit',
                         compiled('length_comparison')), \
            patch.object(ConcreteService, '_compile_character_count_circuit',
                         compiled('character_count')), \
            patch.object(ConcreteService, '_compile_strength_circuit',
                         lambda self: None):
        svc = ConcreteService()
        assert svc.missing_circuits == ['strength']
        assert svc.is_available is False
        assert 'strength' in svc.unavailable_reason


def test_strength_circuit_uses_no_nonexistent_fhe_min():
    source = inspect.getsource(ConcreteService._compile_strength_circuit)
    assert 'fhe.min(' not in source
    assert 'np.minimum' in source


# --------------------------------------------------------------------------
# Router
# --------------------------------------------------------------------------

def test_status_resolves_services_instead_of_reporting_cache():
    """concrete_available used to read the lazily-filled `_concrete`
    attribute, so a fresh router reported False whatever the truth."""
    live = MagicMock(is_available=True)
    live.get_status.return_value = {'available': True}
    with patch('fhe_service.services.fhe_router.get_concrete_service',
               return_value=live), \
            patch('fhe_service.services.fhe_router.get_seal_service',
                  return_value=_unavailable('seal')):
        status = FHEOperationRouter().get_status()
    assert status['concrete_available'] is True
    assert status['fhe_available'] is True


def test_no_backend_routes_plaintext_and_says_so(plaintext_router):
    status = plaintext_router.get_status()
    assert status['fhe_available'] is False
    assert status['concrete']['unavailable_reason'] == 'concrete-python is not installed'
    for op, data in [('strength_check', PASSWORD),
                     ('encrypted_compare', (12, 8)),
                     ('character_count', {'lowercase': 3})]:
        decision, _ = plaintext_router.route_operation(op, data, ComputationalBudget())
        assert decision.tier == EncryptionTier.CLIENT_ONLY
        assert decision.fhe_used is False


def test_backend_fallback_for_one_call_is_not_fhe_used(no_concrete):
    """SEAL reports available but falls back for this call: the tier is
    FULL_FHE, yet the result is plaintext, so fhe_used is False and the
    result is not cached as CACHED_FHE."""
    seal = MagicMock(is_available=True)
    fallback = SEALCiphertext(ciphertext=None, scheme='fallback', created_at=0.0,
                              context_hash='fallback', metadata={'fallback': True})
    seal.encrypt_password_features.return_value = fallback
    seal.simd_strength_evaluation.return_value = (fallback, 42.0)
    cache = MagicMock()
    cache.get.return_value = None
    router = FHEOperationRouter(concrete_service=no_concrete, seal_service=seal,
                                cache=cache)
    decision, _ = router.route_operation('strength_check', PASSWORD,
                                         ComputationalBudget())
    assert decision.tier == EncryptionTier.FULL_FHE
    assert decision.fhe_used is False
    cache.set.assert_not_called()


def test_real_fhe_result_is_fhe_used(no_concrete):
    seal = MagicMock(is_available=True)
    real = SEALCiphertext(ciphertext=object(), scheme='ckks', created_at=0.0,
                          context_hash='ctx', metadata={})
    seal.encrypt_password_features.return_value = real
    seal.simd_strength_evaluation.return_value = (real, 44.0)
    router = FHEOperationRouter(concrete_service=no_concrete, seal_service=seal)
    decision, result = router.route_operation('strength_check', PASSWORD,
                                              ComputationalBudget())
    assert decision.fhe_used is True
    assert result['score'] == 44.0


def test_ops_seal_cannot_run_are_not_upgraded_to_full_fhe(no_concrete):
    """With only SEAL available, compare/character_count used to be routed
    to FULL_FHE, which has no handler for them and returned the plaintext
    input under a FULL_FHE label."""
    router = FHEOperationRouter(concrete_service=no_concrete,
                                seal_service=MagicMock(is_available=True))
    for op, data in [('encrypted_compare', (12, 8)),
                     ('character_count', {'lowercase': 3})]:
        decision, _ = router.route_operation(op, data, ComputationalBudget())
        assert decision.tier == EncryptionTier.CLIENT_ONLY
        assert decision.fhe_used is False


def _similarity_router(no_concrete, scheme):
    seal = MagicMock(is_available=True)
    ct = SEALCiphertext(ciphertext=object(), scheme=scheme, created_at=0.0,
                        context_hash='ctx', metadata={})
    seal.encrypt_password_features.return_value = ct
    seal.batch_encrypt_passwords.return_value = [ct, ct]
    seal.encrypted_similarity_search.return_value = [(0, 0.93)]
    return FHEOperationRouter(concrete_service=no_concrete, seal_service=seal)


def test_similarity_search_under_fhe_is_fhe_used(no_concrete):
    """The SEAL similarity path decrypts its scores, so no ciphertext reaches
    the result; its explicit provenance flag must still count as FHE."""
    router = _similarity_router(no_concrete, 'ckks')
    decision, result = router.route_operation(
        'similarity_search', {'query': PASSWORD, 'vault': ['a1', 'b2']},
        ComputationalBudget(max_latency_ms=2000))
    assert decision.tier == EncryptionTier.FULL_FHE
    assert result['matches'] == [(0, 0.93)]
    assert decision.fhe_used is True


def test_similarity_search_over_fallback_ciphertexts_is_not_fhe(no_concrete):
    router = _similarity_router(no_concrete, 'fallback')
    decision, result = router.route_operation(
        'similarity_search', {'query': PASSWORD, 'vault': ['a1', 'b2']},
        ComputationalBudget(max_latency_ms=2000))
    assert decision.tier == EncryptionTier.FULL_FHE
    assert decision.fhe_used is False


def test_mixed_results_are_not_fhe():
    real = EncryptedValue(b'x', 'op', 0.0, 'h', {'fhe': True})
    fake = EncryptedValue(None, 'op', 0.0, 'plaintext', {'fhe': False})
    assert FHEOperationRouter._result_is_fhe({'a': real}) is True
    assert FHEOperationRouter._result_is_fhe({'a': real, 'b': fake}) is False
    assert FHEOperationRouter._result_is_fhe({'score': 50}) is False


def test_seal_slot_sum_really_sums():
    """_sum_slots called a nonexistent rotate_vector and swallowed the
    error, so the SEAL "score" was slot 0 alone."""
    pytest.importorskip('tenseal')
    from fhe_service.services.seal_service import SEALBatchService
    svc = SEALBatchService()
    assert svc.is_available
    enc = svc.encrypt_password_features(length=11, entropy=11 / 32,
                                        char_diversity=1.0, pattern_score=0.0)
    result, score = svc.simd_strength_evaluation(enc)
    # 0.3*11/32 + 0.4*11/32 + 0.2*1.0 = 0.4406 -> 44.06
    assert score == pytest.approx(44.06, abs=0.1)
    assert result.scheme == 'ckks'


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

@pytest.fixture
def api(db):
    user = User.objects.create_user(username='fhe_user', password='x',
                                    email='fhe@example.com')
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_strength_check_reports_plaintext(api, plaintext_router):
    """`fhe_used` compared 'client_only' to the enum name 'CLIENT_ONLY', so
    every plaintext result was reported as FHE."""
    with patch('fhe_service.views.get_fhe_router', return_value=plaintext_router):
        resp = api.post('/api/fhe/strength-check/',
                        {'password': PASSWORD}, format='json')
    assert resp.status_code == 200
    assert resp.data['fhe_used'] is False
    assert resp.data['tier'] == 'CLIENT_ONLY'
    log = FHEOperationLog.objects.get()
    assert log.encryption_tier == 'client_only'
    assert log.fallback_used is True


@pytest.mark.django_db
def test_strength_check_without_fhe_requested(api):
    resp = api.post('/api/fhe/strength-check/',
                    {'password': PASSWORD, 'use_fhe': False}, format='json')
    assert resp.status_code == 200
    assert resp.data['fhe_used'] is False


@pytest.mark.django_db
def test_encrypt_reports_plaintext(api, plaintext_router):
    with patch('fhe_service.views.get_fhe_router', return_value=plaintext_router):
        resp = api.post('/api/fhe/encrypt/',
                        {'data': PASSWORD, 'operation_type': 'strength_check'},
                        format='json')
    assert resp.status_code == 200
    assert resp.data['fhe_used'] is False
    assert resp.data['tier'] == 'CLIENT_ONLY'


@pytest.mark.django_db
def test_status_reports_concrete_unavailable(api, plaintext_router):
    with patch('fhe_service.views.get_fhe_router', return_value=plaintext_router):
        resp = api.get('/api/fhe/status/')
    assert resp.status_code == 200
    router = resp.data['router']
    assert router['fhe_available'] is False
    assert router['concrete_available'] is False
    assert router['concrete']['unavailable_reason'] == 'concrete-python is not installed'


@pytest.mark.django_db
def test_ml_security_fhe_endpoint_does_not_claim_fhe(api):
    resp = api.post('/api/ml-security/password-strength/fhe/',
                    {'encrypted_password': [1, 2, 3], 'password_length': 14,
                     'metadata': {'isSimulated': False}}, format='json')
    assert resp.status_code == 200
    body = resp.data.get('data', resp.data)
    assert body['fhe_enabled'] is False
    assert body['tier'] == 'length_estimate'
