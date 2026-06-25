"""
Tests for the Bug Bounty external-researcher program (Phase 2).

Covers:
  * the triage state machine (valid transitions, rejected illegal moves)
  * reward issuance + the no-money payout adapter (owed → paid / void)
  * API authorization (owner vs researcher vs stranger) and ownership scoping
  * the submission flow (only active programs accept reports)
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from bug_bounty.models import (
    BountyProgram,
    ProgramStatus,
    Reward,
    RewardStatus,
    Submission,
    SubmissionStatus,
)
from bug_bounty.rewards.adapters import ManualPayoutAdapter, get_payout_adapter
from bug_bounty.services import triage_service

User = get_user_model()


@pytest.fixture
def owner(db):
    # No password: these tests authenticate via force_authenticate(), so a
    # password-login credential would be unused (and trips secret scanners).
    return User.objects.create_user(username='owner')


@pytest.fixture
def researcher(db):
    return User.objects.create_user(username='hacker')


@pytest.fixture
def program(owner):
    return BountyProgram.objects.create(
        owner=owner, title='Vault API Bounty', status=ProgramStatus.ACTIVE,
        scope=['api/vault/'], reward_tiers={'high': 200, 'critical': 500},
    )


@pytest.fixture
def submission(program, researcher):
    return Submission.objects.create(
        program=program, researcher=researcher,
        title='IDOR on vault export', description='details',
        severity_claimed='high',
    )


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# --------------------------------------------------------------------------- #
# Triage state machine (service)
# --------------------------------------------------------------------------- #

def test_full_happy_path_transitions(submission):
    triage_service.apply_transition(submission, SubmissionStatus.TRIAGING)
    assert submission.status == SubmissionStatus.TRIAGING
    triage_service.apply_transition(
        submission, SubmissionStatus.ACCEPTED, severity_assigned='critical',
        note='confirmed',
    )
    assert submission.status == SubmissionStatus.ACCEPTED
    assert submission.severity_assigned == 'critical'
    assert submission.triage_note == 'confirmed'
    triage_service.apply_transition(submission, SubmissionStatus.RESOLVED)
    assert submission.status == SubmissionStatus.RESOLVED


@pytest.mark.parametrize('bad_target', [
    SubmissionStatus.ACCEPTED,   # can't skip triaging
    SubmissionStatus.RESOLVED,   # can't skip to resolved
    SubmissionStatus.REWARDED,   # never via the generic transition
])
def test_illegal_transitions_rejected(submission, bad_target):
    with pytest.raises(triage_service.InvalidTransition):
        triage_service.apply_transition(submission, bad_target)
    submission.refresh_from_db()
    assert submission.status == SubmissionStatus.NEW


def test_terminal_states_have_no_successor(submission):
    triage_service.apply_transition(submission, SubmissionStatus.TRIAGING)
    triage_service.apply_transition(submission, SubmissionStatus.REJECTED)
    with pytest.raises(triage_service.InvalidTransition):
        triage_service.apply_transition(submission, SubmissionStatus.ACCEPTED)


# --------------------------------------------------------------------------- #
# Reward issuance + payout adapter
# --------------------------------------------------------------------------- #

def _resolve(submission):
    triage_service.apply_transition(submission, SubmissionStatus.TRIAGING)
    triage_service.apply_transition(submission, SubmissionStatus.ACCEPTED)
    triage_service.apply_transition(submission, SubmissionStatus.RESOLVED)


def test_issue_reward_creates_owed_obligation(submission):
    _resolve(submission)
    reward = triage_service.issue_reward(submission, amount=Decimal('200.00'))
    submission.refresh_from_db()
    assert submission.status == SubmissionStatus.REWARDED
    assert reward.status == RewardStatus.OWED
    assert reward.amount == Decimal('200.00')
    assert reward.payout_ref == ''  # nothing paid yet


def test_cannot_reward_before_resolved(submission):
    with pytest.raises(triage_service.InvalidTransition):
        triage_service.issue_reward(submission, amount=Decimal('50.00'))


def test_cannot_reward_twice(submission):
    _resolve(submission)
    triage_service.issue_reward(submission, amount=Decimal('200.00'))
    with pytest.raises(triage_service.InvalidTransition):
        triage_service.issue_reward(submission, amount=Decimal('200.00'))


def test_pay_reward_uses_adapter_and_moves_no_money(submission):
    _resolve(submission)
    reward = triage_service.issue_reward(submission, amount=Decimal('200.00'))
    triage_service.pay_reward(reward)
    reward.refresh_from_db()
    assert reward.status == RewardStatus.PAID
    # The manual adapter only records an off-platform reference — no processor.
    assert reward.payout_ref == f'manual:{reward.id}'
    assert reward.paid_at is not None


def test_paid_reward_cannot_be_paid_again_or_voided(submission):
    _resolve(submission)
    reward = triage_service.issue_reward(submission, amount=Decimal('200.00'))
    triage_service.pay_reward(reward)
    with pytest.raises(triage_service.InvalidTransition):
        triage_service.pay_reward(reward)
    with pytest.raises(triage_service.InvalidTransition):
        triage_service.void_reward(reward)


def test_void_reward(submission):
    _resolve(submission)
    reward = triage_service.issue_reward(submission, amount=Decimal('200.00'))
    triage_service.void_reward(reward)
    reward.refresh_from_db()
    assert reward.status == RewardStatus.VOID


def test_get_payout_adapter_defaults_to_manual():
    assert isinstance(get_payout_adapter('manual'), ManualPayoutAdapter)
    assert isinstance(get_payout_adapter('does-not-exist'), ManualPayoutAdapter)
    assert isinstance(get_payout_adapter(None), ManualPayoutAdapter)


# --------------------------------------------------------------------------- #
# Program API — ownership scoping
# --------------------------------------------------------------------------- #

def _items(data):
    return data['results'] if isinstance(data, dict) and 'results' in data else data


def test_programs_are_owner_scoped(owner, researcher, program):
    resp = _client(researcher).get('/api/bug-bounty/programs/')
    assert resp.status_code == 200
    assert list(_items(resp.data)) == []  # researcher sees none of owner's programs

    resp = _client(owner).get('/api/bug-bounty/programs/')
    assert [p['title'] for p in _items(resp.data)] == ['Vault API Bounty']


def test_create_program_sets_owner_from_request(owner):
    resp = _client(owner).post('/api/bug-bounty/programs/', {
        'title': 'New Program', 'status': 'active', 'scope': ['auth/'],
        'reward_tiers': {'high': 100},
    }, format='json')
    assert resp.status_code == 201
    program = BountyProgram.objects.get(id=resp.data['id'])
    assert program.owner == owner


def test_reward_tiers_validation_rejects_bad_severity(owner):
    resp = _client(owner).post('/api/bug-bounty/programs/', {
        'title': 'Bad tiers', 'reward_tiers': {'nope': 100},
    }, format='json')
    assert resp.status_code == 400


def test_available_lists_active_programs_across_owners(researcher, program):
    resp = _client(researcher).get('/api/bug-bounty/programs/available/')
    assert resp.status_code == 200
    titles = [p['title'] for p in resp.data]
    assert 'Vault API Bounty' in titles


def test_available_excludes_non_active(owner, researcher):
    BountyProgram.objects.create(
        owner=owner, title='Draft prog', status=ProgramStatus.DRAFT,
    )
    resp = _client(researcher).get('/api/bug-bounty/programs/available/')
    assert 'Draft prog' not in [p['title'] for p in resp.data]


# --------------------------------------------------------------------------- #
# Submission API
# --------------------------------------------------------------------------- #

def test_researcher_can_submit_to_active_program(researcher, program):
    resp = _client(researcher).post('/api/bug-bounty/submissions/', {
        'program': str(program.id), 'title': 'XSS', 'description': 'repro',
        'severity_claimed': 'medium',
    }, format='json')
    assert resp.status_code == 201
    sub = Submission.objects.get(id=resp.data['id'])
    assert sub.researcher == researcher
    assert sub.status == SubmissionStatus.NEW


def test_cannot_submit_to_inactive_program(owner, researcher):
    paused = BountyProgram.objects.create(
        owner=owner, title='Paused', status=ProgramStatus.PAUSED,
    )
    resp = _client(researcher).post('/api/bug-bounty/submissions/', {
        'program': str(paused.id), 'title': 'x', 'description': 'y',
    }, format='json')
    assert resp.status_code == 400


def test_submission_visible_to_researcher_and_owner_only(owner, researcher, submission):
    stranger = User.objects.create_user(username='eve')

    for user in (owner, researcher):
        resp = _client(user).get(f'/api/bug-bounty/submissions/{submission.id}/')
        assert resp.status_code == 200

    resp = _client(stranger).get(f'/api/bug-bounty/submissions/{submission.id}/')
    assert resp.status_code == 404  # not in stranger's queryset → no leakage


# --------------------------------------------------------------------------- #
# Triage API authorization
# --------------------------------------------------------------------------- #

def test_owner_can_transition_via_api(owner, submission):
    resp = _client(owner).post(
        f'/api/bug-bounty/submissions/{submission.id}/transition/',
        {'to_status': 'triaging'}, format='json',
    )
    assert resp.status_code == 200
    submission.refresh_from_db()
    assert submission.status == SubmissionStatus.TRIAGING


def test_researcher_cannot_transition(researcher, submission):
    resp = _client(researcher).post(
        f'/api/bug-bounty/submissions/{submission.id}/transition/',
        {'to_status': 'triaging'}, format='json',
    )
    assert resp.status_code == 403
    submission.refresh_from_db()
    assert submission.status == SubmissionStatus.NEW


def test_invalid_transition_returns_400(owner, submission):
    resp = _client(owner).post(
        f'/api/bug-bounty/submissions/{submission.id}/transition/',
        {'to_status': 'resolved'}, format='json',  # illegal from NEW
    )
    assert resp.status_code == 400


def test_reward_flow_via_api(owner, researcher, submission):
    client = _client(owner)
    for to in ('triaging', 'accepted', 'resolved'):
        client.post(
            f'/api/bug-bounty/submissions/{submission.id}/transition/',
            {'to_status': to}, format='json',
        )
    resp = client.post(
        f'/api/bug-bounty/submissions/{submission.id}/reward/',
        {'amount': '200.00', 'currency': 'usd'}, format='json',
    )
    assert resp.status_code == 201
    reward = Reward.objects.get(id=resp.data['id'])
    assert reward.status == RewardStatus.OWED
    assert reward.currency == 'USD'  # normalised by the serializer

    # Researcher can see the reward but cannot pay it.
    resp = _client(researcher).post(f'/api/bug-bounty/rewards/{reward.id}/pay/')
    assert resp.status_code == 403

    # Owner pays through the adapter (no money moves).
    resp = client.post(f'/api/bug-bounty/rewards/{reward.id}/pay/')
    assert resp.status_code == 200
    reward.refresh_from_db()
    assert reward.status == RewardStatus.PAID
    assert reward.payout_ref == f'manual:{reward.id}'


def test_reward_before_resolved_returns_400(owner, submission):
    resp = _client(owner).post(
        f'/api/bug-bounty/submissions/{submission.id}/reward/',
        {'amount': '50.00'}, format='json',
    )
    assert resp.status_code == 400


def test_rewards_are_visibility_scoped(owner, researcher, submission):
    stranger = User.objects.create_user(username='mallory')
    _resolve(submission)
    reward = triage_service.issue_reward(submission, amount=Decimal('200.00'))

    resp = _client(stranger).get(f'/api/bug-bounty/rewards/{reward.id}/')
    assert resp.status_code == 404
    resp = _client(researcher).get(f'/api/bug-bounty/rewards/{reward.id}/')
    assert resp.status_code == 200
