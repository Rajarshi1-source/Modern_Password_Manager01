"""Unit + integration tests for the personality_auth app.

Covers:
* Privacy opt-in gate against ``UserPreferences.privacy_analytics``.
* Claude JSON adapter schema validation (happy path + retry-on-bad-json).
* Inference pipeline with a stubbed Claude service.
* Question generator producing ``PersonalityQuestion`` rows from mocked LLM JSON.
* Consistency scorer branches (top / avoid / keyword / latency).
* Challenge orchestrator lifecycle (pending -> in_progress -> passed/failed).
* Rate limiting (cache-backed).
* DRF endpoints (opt-in, start challenge, submit answer, audit).
"""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from personality_auth.models import (
    AuditEventType,
    ChallengeStatus,
    MoodContext,
    PersonalityAuditLog,
    PersonalityChallenge,
    PersonalityProfile,
    PersonalityQuestion,
    PersonalityResponse,
    QuestionDimension,
)
from personality_auth.services import (
    ChallengeOrchestrator,
    ClaudeJSONAdapter,
    ConsistencyScorerService,
    GenerationPlan,
    LLMSchemaError,
    PersonalityInferenceService,
    QuestionGeneratorService,
    RateLimited,
    AdapterCall,
    user_opted_in,
)
from personality_auth.services.challenge_orchestrator import RATE_LIMIT_CACHE_PREFIX
from user.models import UserPreferences


User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def user(db):
    u = User.objects.create_user(
        email='persona@example.com', password='Testp4ss!!'
    )
    # Default: analytics OFF so opt-in gate tests can flip it explicitly.
    prefs, _ = UserPreferences.objects.get_or_create(user=u)
    prefs.privacy_analytics = False
    prefs.save()
    return u


@pytest.fixture
def analytics_user(user):
    prefs = user.preferences
    prefs.privacy_analytics = True
    prefs.save()
    return user


@pytest.fixture
def profile(analytics_user):
    return PersonalityProfile.objects.create(
        user=analytics_user,
        opted_in=True,
        opt_in_changed_at=timezone.now(),
        trait_features={'openness': 0.7, 'conscientiousness': 0.5},
        theme_weights=[{'label': 'astronomy', 'weight': 0.7}],
    )


@pytest.fixture
def api_client(analytics_user):
    client = APIClient()
    client.force_authenticate(analytics_user)
    return client


# ---------------------------------------------------------------------------
# Privacy gate
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_user_opted_in_reflects_privacy_analytics_flag(user):
    assert user_opted_in(user) is False
    user.preferences.privacy_analytics = True
    user.preferences.save()
    assert user_opted_in(user) is True


@pytest.mark.django_db
def test_infer_rejects_user_without_opt_in(user):
    with pytest.raises(PermissionError):
        PersonalityInferenceService(adapter=_fake_inference_adapter()).infer(user)


# ---------------------------------------------------------------------------
# Claude JSON adapter
# ---------------------------------------------------------------------------

class _StubClaudeService:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def send_message(self, user, conversation_history=None, user_message='', vault_context=None):
        self.calls.append(user_message)
        if not self._responses:
            return {'content': ''}
        return {'content': self._responses.pop(0)}


def test_claude_json_adapter_parses_fenced_json():
    stub = _StubClaudeService(['```json\n{"answer": 42}\n```'])
    adapter = ClaudeJSONAdapter(stub)
    result = adapter.call(AdapterCall(prompt='x', schema={'required': ['answer']}))
    assert result['answer'] == 42


def test_claude_json_adapter_retries_on_malformed():
    stub = _StubClaudeService(['not json at all', '{"answer": 7}'])
    adapter = ClaudeJSONAdapter(stub)
    result = adapter.call(AdapterCall(prompt='x', schema={'required': ['answer']}))
    assert result['answer'] == 7
    assert len(stub.calls) == 2


def test_claude_json_adapter_raises_after_max_attempts():
    stub = _StubClaudeService(['not json', 'still not json'])
    adapter = ClaudeJSONAdapter(stub)
    with pytest.raises(LLMSchemaError):
        adapter.call(AdapterCall(prompt='x', schema={'required': ['answer']}))


def test_claude_json_adapter_callable_validator_raises_on_error():
    stub = _StubClaudeService(['{"x": 1}', '{"x": 1}'])
    adapter = ClaudeJSONAdapter(stub)

    def validator(data):
        raise ValueError('nope')

    with pytest.raises(LLMSchemaError):
        adapter.call(AdapterCall(prompt='x', schema=validator))


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def _fake_inference_adapter(payload=None):
    payload = payload or {
        'traits': {'openness': 0.8, 'conscientiousness': 0.6},
        'themes': [{'label': 'astronomy', 'weight': 0.7}],
        'moral_framework': {'care': 0.9, 'fairness': 0.8},
        'value_tags': ['curiosity', 'honesty'],
        'confidence': 0.82,
    }
    stub = _StubClaudeService([json.dumps(payload)])
    return ClaudeJSONAdapter(stub)


@pytest.mark.django_db
def test_inference_upserts_profile_and_snapshot(analytics_user):
    with patch('personality_auth.services.inference_service.PersonalityInferenceService._collect_messages') as mock_collect:
        mock_collect.return_value = ['msg1', 'msg2', 'msg3']
        service = PersonalityInferenceService(adapter=_fake_inference_adapter())
        result = service.infer(analytics_user)

    profile = PersonalityProfile.objects.get(user=analytics_user)
    assert profile.trait_features['openness'] == pytest.approx(0.8)
    assert profile.source_messages_analysed == 3
    assert result.confidence == pytest.approx(0.82)
    assert result.snapshot.coefficients['care'] == pytest.approx(0.9)

    audit_events = list(
        PersonalityAuditLog.objects.filter(profile=profile).values_list('event_type', flat=True)
    )
    assert AuditEventType.PROFILE_INFERRED in audit_events


@pytest.mark.django_db
def test_inference_no_messages_yields_empty_snapshot(analytics_user):
    with patch('personality_auth.services.inference_service.PersonalityInferenceService._collect_messages') as mock_collect:
        mock_collect.return_value = []
        service = PersonalityInferenceService(adapter=_fake_inference_adapter())
        result = service.infer(analytics_user)

    assert result.sample_size == 0
    assert result.confidence == 0.0
    assert result.snapshot.coefficients == {}


# ---------------------------------------------------------------------------
# Question generator
# ---------------------------------------------------------------------------

def _fake_question_adapter():
    payload = json.dumps([
        {
            'prompt': 'Which choice feels most like you?',
            'choices': ['curious', 'cautious', 'competitive'],
            'expected_signature': {'top': 'a', 'avoid': ['c']},
            'rationale': 'maps to openness dimension',
        }
    ])
    return ClaudeJSONAdapter(_StubClaudeService([payload] * 10))


@pytest.mark.django_db
def test_question_generator_creates_rows(profile):
    generator = QuestionGeneratorService(adapter=_fake_question_adapter())
    created = generator.generate(
        profile,
        plans=[GenerationPlan(QuestionDimension.VALUES, PersonalityQuestion.DIFFICULTY_MEDIUM, 1)],
    )
    assert len(created) == 1
    q = created[0]
    assert q.profile == profile
    assert q.dimension == QuestionDimension.VALUES
    assert q.choices == ['curious', 'cautious', 'competitive']
    assert q.expected_signature['top'] == 'a'


@pytest.mark.django_db
def test_question_generator_skips_plan_on_schema_error(profile):
    bad_adapter = ClaudeJSONAdapter(_StubClaudeService(['not json', 'still not json']))
    good_plan_payload = json.dumps([
        {
            'prompt': 'x?',
            'choices': ['one', 'two'],
            'expected_signature': {'top': 'b'},
            'rationale': 'y',
        }
    ])

    # Per-plan responses: first plan fails both attempts, second plan succeeds.
    stub = _StubClaudeService(['not json', 'not json', good_plan_payload, good_plan_payload])
    generator = QuestionGeneratorService(adapter=ClaudeJSONAdapter(stub))
    created = generator.generate(
        profile,
        plans=[
            GenerationPlan(QuestionDimension.VALUES, 1, 1),
            GenerationPlan(QuestionDimension.STYLE, 1, 1),
        ],
    )
    assert len(created) == 1
    assert created[0].dimension == QuestionDimension.STYLE

    error_events = PersonalityAuditLog.objects.filter(
        profile=profile, event_type=AuditEventType.MODEL_ERROR
    )
    assert error_events.exists()


# ---------------------------------------------------------------------------
# Consistency scorer
# ---------------------------------------------------------------------------

def _make_question(profile, expected_signature, choices=None):
    return PersonalityQuestion.objects.create(
        profile=profile,
        dimension=QuestionDimension.VALUES,
        prompt='prompt',
        choices=choices or ['curious', 'cautious', 'competitive'],
        expected_signature=expected_signature,
    )


@pytest.mark.django_db
def test_scorer_rewards_top_choice(profile):
    q = _make_question(profile, {'top': 'a'})
    result = ConsistencyScorerService().score(q, answer_choice='a')
    assert result.score >= 0.65
    assert not result.hard_fail


@pytest.mark.django_db
def test_scorer_hard_fails_on_avoid_choice(profile):
    q = _make_question(profile, {'top': 'a', 'avoid': ['c']})
    result = ConsistencyScorerService().score(q, answer_choice='c')
    assert result.hard_fail
    assert result.score == 0.0


@pytest.mark.django_db
def test_scorer_gives_partial_credit_for_keywords(profile):
    q = _make_question(profile, {'top': 'a', 'keywords': ['family', 'honesty']})
    result = ConsistencyScorerService().score(
        q, answer_text='I believe in family and honesty above all'
    )
    assert result.score >= 0.4


@pytest.mark.django_db
def test_scorer_latency_penalty(profile):
    q = _make_question(profile, {'top': 'a'})
    fast = ConsistencyScorerService().score(q, answer_choice='a', latency_ms=50)
    normal = ConsistencyScorerService().score(q, answer_choice='a', latency_ms=2000)
    assert fast.score < normal.score


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_orchestrator_rejects_non_opted_in_user(user):
    with pytest.raises(PermissionError):
        ChallengeOrchestrator().start_challenge(user)


@pytest.mark.django_db
def test_orchestrator_full_passing_flow(profile):
    cache.clear()
    for dim in (QuestionDimension.VALUES, QuestionDimension.BELIEFS, QuestionDimension.STYLE):
        PersonalityQuestion.objects.create(
            profile=profile,
            dimension=dim,
            prompt=f'probe {dim}',
            choices=['opt1', 'opt2'],
            expected_signature={'top': 'a'},
        )

    orchestrator = ChallengeOrchestrator()
    prepared = orchestrator.start_challenge(profile.user, question_count=3)
    assert prepared.challenge.status == ChallengeStatus.IN_PROGRESS
    assert len(prepared.questions) == 3

    last_result = None
    for q in prepared.questions:
        last_result = orchestrator.submit_response(prepared.challenge, q, answer_choice='a', latency_ms=1200)

    prepared.challenge.refresh_from_db()
    assert prepared.challenge.status == ChallengeStatus.PASSED
    assert last_result.finished is True
    assert last_result.passed is True
    assert prepared.challenge.achieved_score is not None


@pytest.mark.django_db
def test_orchestrator_hard_fail_short_circuits(profile):
    cache.clear()
    q_bad = PersonalityQuestion.objects.create(
        profile=profile,
        dimension=QuestionDimension.VALUES,
        prompt='probe values',
        choices=['opt1', 'opt2', 'opt3'],
        expected_signature={'top': 'a', 'avoid': ['c']},
    )
    PersonalityQuestion.objects.create(
        profile=profile,
        dimension=QuestionDimension.BELIEFS,
        prompt='probe beliefs',
        choices=['opt1', 'opt2'],
        expected_signature={'top': 'a'},
    )

    orchestrator = ChallengeOrchestrator()
    prepared = orchestrator.start_challenge(profile.user, question_count=2)
    bad_in_challenge = [q for q in prepared.questions if q.id == q_bad.id]
    if not bad_in_challenge:
        q_bad = prepared.questions[0]
        q_bad.expected_signature = {'top': 'a', 'avoid': ['c']}
        q_bad.save()

    result = orchestrator.submit_response(prepared.challenge, q_bad, answer_choice='c')
    prepared.challenge.refresh_from_db()
    assert result.finished is True
    assert result.passed is False
    assert prepared.challenge.status == ChallengeStatus.FAILED


@pytest.mark.django_db
def test_orchestrator_rate_limits(profile, monkeypatch):
    cache.clear()
    PersonalityQuestion.objects.create(
        profile=profile,
        dimension=QuestionDimension.VALUES,
        prompt='probe',
        choices=['opt'],
        expected_signature={'top': 'a'},
    )

    orchestrator = ChallengeOrchestrator()
    # Seed cache to max.
    cache.set(f"{RATE_LIMIT_CACHE_PREFIX}:{profile.user.pk}", 999, timeout=900)
    with pytest.raises(RateLimited):
        orchestrator.start_challenge(profile.user)


@pytest.mark.django_db
def test_orchestrator_marks_expired_challenge(profile):
    cache.clear()
    q = PersonalityQuestion.objects.create(
        profile=profile,
        dimension=QuestionDimension.VALUES,
        prompt='probe',
        choices=['opt'],
        expected_signature={'top': 'a'},
    )
    challenge = PersonalityChallenge.objects.create(
        profile=profile,
        status=ChallengeStatus.IN_PROGRESS,
        expires_at=timezone.now() - timedelta(minutes=1),
    )
    challenge.questions.add(q)

    with pytest.raises(ValueError):
        ChallengeOrchestrator().submit_response(challenge, q, answer_choice='a')

    challenge.refresh_from_db()
    assert challenge.status == ChallengeStatus.EXPIRED


# ---------------------------------------------------------------------------
# DRF endpoints
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_profile_endpoint_unauth_returns_empty(api_client, analytics_user):
    resp = api_client.get('/api/personality/profile/')
    assert resp.status_code == 200
    assert resp.json()['opted_in'] in (False, True)


@pytest.mark.django_db
def test_opt_in_requires_analytics_flag(user):
    client = APIClient()
    client.force_authenticate(user)
    resp = client.post('/api/personality/opt-in/', {'opted_in': True}, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_opt_in_success_creates_profile(api_client, analytics_user):
    resp = api_client.post('/api/personality/opt-in/', {'opted_in': True}, format='json')
    assert resp.status_code == 200
    assert PersonalityProfile.objects.filter(user=analytics_user, opted_in=True).exists()


@pytest.mark.django_db
def test_start_challenge_requires_questions(api_client, profile):
    cache.clear()
    resp = api_client.post('/api/personality/challenges/start/', {}, format='json')
    assert resp.status_code == 409


@pytest.mark.django_db
def test_start_and_submit_challenge_via_api(api_client, profile):
    cache.clear()
    for dim in (QuestionDimension.VALUES, QuestionDimension.BELIEFS):
        PersonalityQuestion.objects.create(
            profile=profile,
            dimension=dim,
            prompt=f'probe {dim}',
            choices=['opt1', 'opt2'],
            expected_signature={'top': 'a'},
        )

    resp = api_client.post(
        '/api/personality/challenges/start/',
        {'question_count': 2},
        format='json',
    )
    assert resp.status_code == 201, resp.content
    challenge_data = resp.json()
    challenge_id = challenge_data['id']
    assert len(challenge_data['questions']) == 2

    last_status = None
    for q in challenge_data['questions']:
        submit = api_client.post(
            f'/api/personality/challenges/{challenge_id}/submit/',
            {'question_id': q['id'], 'answer_choice': 'a', 'latency_ms': 1500},
            format='json',
        )
        assert submit.status_code == 200, submit.content
        last_status = submit.json()

    assert last_status['finished'] is True
    assert last_status['passed'] is True


@pytest.mark.django_db
def test_audit_endpoint_returns_entries(api_client, profile):
    from personality_auth.services.audit_service import record_event
    record_event(profile, AuditEventType.PROFILE_INFERRED, {'test': True})

    resp = api_client.get('/api/personality/audit/')
    assert resp.status_code == 200
    data = resp.json()
    assert any(e['event_type'] == AuditEventType.PROFILE_INFERRED for e in data)


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_prune_expired_questions_task(profile):
    from personality_auth.tasks import prune_expired_questions

    live = PersonalityQuestion.objects.create(
        profile=profile,
        dimension=QuestionDimension.VALUES,
        prompt='live',
        choices=['a'],
        expected_signature={'top': 'a'},
        expires_at=timezone.now() + timedelta(hours=1),
    )
    dead = PersonalityQuestion.objects.create(
        profile=profile,
        dimension=QuestionDimension.BELIEFS,
        prompt='dead',
        choices=['a'],
        expected_signature={'top': 'a'},
        expires_at=timezone.now() - timedelta(hours=1),
    )
    stale_challenge = PersonalityChallenge.objects.create(
        profile=profile,
        status=ChallengeStatus.IN_PROGRESS,
        expires_at=timezone.now() - timedelta(minutes=1),
    )

    result = prune_expired_questions()
    assert result['questions_deleted'] >= 1
    assert result['challenges_expired'] >= 1
    assert not PersonalityQuestion.objects.filter(id=dead.id).exists()
    assert PersonalityQuestion.objects.filter(id=live.id).exists()
    stale_challenge.refresh_from_db()
    assert stale_challenge.status == ChallengeStatus.EXPIRED
