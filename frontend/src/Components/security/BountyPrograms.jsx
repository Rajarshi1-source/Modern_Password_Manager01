/**
 * Bug Bounty — Bounty Program panel (Phase 2)
 * ===========================================
 *
 * The external-researcher surface that sits alongside the self-pentest:
 *
 *   • Owner view  — create/manage programs and triage their submissions
 *                   through the state machine (triage → accept → resolve →
 *                   reward), then record/settle rewards via the payout adapter.
 *   • Research view — browse active programs and file reports against them.
 *
 * No money moves in-product: a reward is a recorded obligation, and "Pay" only
 * marks it settled off-platform through the manual adapter. Researchers test the
 * app's attack surface — never any user's vault data.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import styled from 'styled-components';
import {
  getPrograms,
  getAvailablePrograms,
  createProgram,
  updateProgram,
  getSubmissions,
  createSubmission,
  transitionSubmission,
  rewardSubmission,
  payReward,
  voidReward,
} from '../../services/bugBountyService';

const SEVERITIES = ['info', 'low', 'medium', 'high', 'critical'];
const SEVERITY_COLOR = {
  critical: '#dc2626',
  high: '#ef4444',
  medium: '#f59e0b',
  low: '#3b82f6',
  info: '#6b7280',
};
const PROGRAM_STATUS = ['draft', 'active', 'paused', 'closed'];

// Triage moves offered for each submission status (mirrors the backend state
// machine in services/triage_service.py).
const NEXT_ACTIONS = {
  new: [{ to: 'triaging', label: 'Start triage' }],
  triaging: [
    { to: 'accepted', label: 'Accept' },
    { to: 'duplicate', label: 'Duplicate' },
    { to: 'rejected', label: 'Reject' },
  ],
  accepted: [{ to: 'resolved', label: 'Mark resolved' }],
};

const Wrap = styled.div``;

const SubTabs = styled.div`
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
`;

const SubTab = styled.button`
  border: 1px solid ${(p) => p.theme.borderColor || 'rgba(127,127,127,0.3)'};
  background: ${(p) => (p.$active ? 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)' : 'transparent')};
  color: ${(p) => (p.$active ? '#fff' : p.theme.textSecondary || '#9ca3af')};
  border-radius: 8px;
  padding: 8px 16px;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
`;

const Card = styled.div`
  border: 1px solid ${(p) => p.theme.borderColor || 'rgba(127,127,127,0.25)'};
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 14px;
  background: ${(p) => p.theme.cardBg || 'transparent'};
`;

const Row = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
`;

const Title = styled.h3`
  font-size: 16px;
  margin: 0;
`;

const Badge = styled.span`
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 3px 9px;
  border-radius: 999px;
  color: #fff;
  background: ${(p) => p.$color || '#6b7280'};
`;

const Muted = styled.p`
  color: ${(p) => p.theme.textSecondary || '#9ca3af'};
  font-size: 13px;
  margin: 6px 0 0;
  line-height: 1.5;
`;

const Button = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid ${(p) => p.theme.borderColor || 'rgba(127,127,127,0.3)'};
  background: ${(p) => (p.$primary ? 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)' : 'transparent')};
  color: ${(p) => (p.$primary ? '#fff' : p.theme.textSecondary || '#9ca3af')};
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  &:disabled { opacity: 0.5; cursor: not-allowed; }
`;

const Field = styled.label`
  display: block;
  font-size: 13px;
  font-weight: 600;
  margin: 10px 0 4px;
  color: ${(p) => p.theme.textSecondary || '#9ca3af'};
`;

const Input = styled.input`
  width: 100%;
  box-sizing: border-box;
  border: 1px solid ${(p) => p.theme.borderColor || 'rgba(127,127,127,0.3)'};
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 14px;
  background: transparent;
  color: inherit;
`;

const TextArea = styled(Input).attrs({ as: 'textarea' })`
  min-height: 72px;
  resize: vertical;
`;

const Select = styled(Input).attrs({ as: 'select' })``;

const ActionBar = styled.div`
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
`;

const Alert = styled.p`
  color: ${(p) => (p.$ok ? '#10b981' : '#ef4444')};
  font-size: 13px;
  margin: 8px 0;
`;

const Empty = styled.div`
  text-align: center;
  padding: 28px 16px;
  color: ${(p) => p.theme.textSecondary || '#9ca3af'};
`;

const StatusBadge = ({ status, kind = 'program' }) => {
  const colors = {
    program: { active: '#10b981', draft: '#6b7280', paused: '#f59e0b', closed: '#374151' },
    submission: {
      new: '#3b82f6', triaging: '#f59e0b', accepted: '#10b981',
      duplicate: '#6b7280', rejected: '#ef4444', resolved: '#8b5cf6', rewarded: '#22c55e',
    },
    reward: { owed: '#f59e0b', paid: '#10b981', void: '#6b7280' },
  };
  return <Badge $color={(colors[kind] || {})[status] || '#6b7280'}>{status}</Badge>;
};

// --------------------------------------------------------------------------- //
// Owner: create-program form
// --------------------------------------------------------------------------- //

const CreateProgramForm = ({ onCreated }) => {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [scope, setScope] = useState('');
  const [policy, setPolicy] = useState('');
  const [status, setStatus] = useState('active');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await createProgram({
        title: title.trim(),
        status,
        policy: policy.trim(),
        scope: scope.split('\n').map((s) => s.trim()).filter(Boolean),
      });
      setTitle(''); setScope(''); setPolicy('');
      setOpen(false);
      onCreated(created);
    } catch {
      setError('Could not create the program. Check the fields and try again.');
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return <Button $primary type="button" onClick={() => setOpen(true)}>+ New program</Button>;
  }
  return (
    <Card>
      <Title>New bounty program</Title>
      <Field htmlFor="bp-title">Title</Field>
      <Input id="bp-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Vault API Bounty" />
      <Field htmlFor="bp-scope">In-scope targets (one per line)</Field>
      <TextArea id="bp-scope" value={scope} onChange={(e) => setScope(e.target.value)} placeholder={'api/vault/\nauth login flow'} />
      <Field htmlFor="bp-policy">Disclosure policy / rules</Field>
      <TextArea id="bp-policy" value={policy} onChange={(e) => setPolicy(e.target.value)} placeholder="Report privately. No DoS. No accessing other users' data." />
      <Field htmlFor="bp-status">Status</Field>
      <Select id="bp-status" value={status} onChange={(e) => setStatus(e.target.value)}>
        {PROGRAM_STATUS.map((s) => <option key={s} value={s}>{s}</option>)}
      </Select>
      {error && <Alert>{error}</Alert>}
      <ActionBar>
        <Button $primary type="button" onClick={submit} disabled={busy || !title.trim()}>
          {busy ? 'Creating…' : 'Create'}
        </Button>
        <Button type="button" onClick={() => setOpen(false)} disabled={busy}>Cancel</Button>
      </ActionBar>
    </Card>
  );
};

// --------------------------------------------------------------------------- //
// Owner: a single submission with triage controls
// --------------------------------------------------------------------------- //

const SubmissionRow = ({ submission, onChanged }) => {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [severity, setSeverity] = useState(submission.severity_claimed || 'medium');
  const [amount, setAmount] = useState('');

  const run = async (fn) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onChanged();
    } catch (e) {
      const detail = e?.response?.data;
      const msg = detail?.detail
        || (Array.isArray(detail?.non_field_errors) ? detail.non_field_errors[0] : null)
        || 'Action failed. Please try again.';
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const actions = NEXT_ACTIONS[submission.status] || [];
  const reward = submission.reward;

  return (
    <Card>
      <Row>
        <Title>{submission.title}</Title>
        <StatusBadge status={submission.status} kind="submission" />
      </Row>
      <Muted>
        by <strong>{submission.researcher_username}</strong> · claimed{' '}
        <Badge $color={SEVERITY_COLOR[submission.severity_claimed]}>{submission.severity_claimed}</Badge>
        {submission.severity_assigned ? (
          <> · assigned <Badge $color={SEVERITY_COLOR[submission.severity_assigned]}>{submission.severity_assigned}</Badge></>
        ) : null}
      </Muted>
      {submission.description && <Muted>{submission.description}</Muted>}

      {submission.status === 'triaging' && (
        <>
          <Field htmlFor={`sev-${submission.id}`}>Assign severity (on accept)</Field>
          <Select id={`sev-${submission.id}`} value={severity} onChange={(e) => setSeverity(e.target.value)}>
            {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
          </Select>
        </>
      )}

      {submission.status === 'resolved' && !reward && (
        <>
          <Field htmlFor={`amt-${submission.id}`}>Reward amount (USD)</Field>
          <Input
            id={`amt-${submission.id}`}
            type="number"
            min="0.01"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="200.00"
          />
        </>
      )}

      {error && <Alert>{error}</Alert>}

      <ActionBar>
        {actions.map((a) => (
          <Button
            key={a.to}
            type="button"
            disabled={busy}
            onClick={() => run(() => transitionSubmission(submission.id, {
              to_status: a.to,
              ...(a.to === 'accepted' ? { severity_assigned: severity } : {}),
            }))}
          >
            {a.label}
          </Button>
        ))}
        {submission.status === 'resolved' && !reward && (
          <Button
            $primary
            type="button"
            disabled={busy || !(Number(amount) > 0)}
            onClick={() => run(() => rewardSubmission(submission.id, { amount, currency: 'USD' }))}
          >
            Issue reward
          </Button>
        )}
      </ActionBar>

      {reward && (
        <Card style={{ marginTop: 12, marginBottom: 0 }}>
          <Row>
            <span>Reward: <strong>{reward.amount} {reward.currency}</strong></span>
            <StatusBadge status={reward.status} kind="reward" />
          </Row>
          {reward.payout_ref && <Muted>Ref: {reward.payout_ref}</Muted>}
          {reward.status === 'owed' && (
            <ActionBar>
              <Button $primary type="button" disabled={busy} onClick={() => run(() => payReward(reward.id))}>
                Mark paid (off-platform)
              </Button>
              <Button type="button" disabled={busy} onClick={() => run(() => voidReward(reward.id))}>
                Void
              </Button>
            </ActionBar>
          )}
        </Card>
      )}
    </Card>
  );
};

// --------------------------------------------------------------------------- //
// Owner view
// --------------------------------------------------------------------------- //

const OwnerView = () => {
  const [programs, setPrograms] = useState([]);
  const [submissions, setSubmissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const [progs, subs] = await Promise.all([getPrograms(), getSubmissions()]);
      setPrograms(progs.results || progs);
      setSubmissions(subs.results || subs);
    } catch {
      setError('Could not load your programs.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggleStatus = async (program) => {
    const next = program.status === 'active' ? 'paused' : 'active';
    try {
      await updateProgram(program.id, { status: next });
      load();
    } catch {
      setError('Could not update the program status.');
    }
  };

  // Group submissions by program for display under each program.
  const subsByProgram = useMemo(() => {
    const map = {};
    submissions.forEach((s) => {
      (map[s.program] = map[s.program] || []).push(s);
    });
    return map;
  }, [submissions]);

  if (loading) return <Muted>Loading programs…</Muted>;

  return (
    <Wrap>
      <Row style={{ marginBottom: 16 }}>
        <Muted style={{ margin: 0 }}>Define a program and triage incoming reports.</Muted>
        <CreateProgramForm onCreated={load} />
      </Row>
      {error && <Alert>{error}</Alert>}

      {programs.length === 0 ? (
        <Empty>No programs yet. Create one to start accepting reports.</Empty>
      ) : (
        programs.map((program) => {
          const subs = subsByProgram[program.id] || [];
          return (
            <Card key={program.id}>
              <Row>
                <Title>{program.title}</Title>
                <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
                  <StatusBadge status={program.status} kind="program" />
                  <Button type="button" onClick={() => toggleStatus(program)}>
                    {program.status === 'active' ? 'Pause' : 'Activate'}
                  </Button>
                </span>
              </Row>
              {program.scope?.length > 0 && <Muted>Scope: {program.scope.join(', ')}</Muted>}
              <Muted>{program.submission_count ?? subs.length} submission(s)</Muted>

              {subs.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  {subs.map((s) => (
                    <SubmissionRow key={s.id} submission={s} onChanged={load} />
                  ))}
                </div>
              )}
            </Card>
          );
        })
      )}
    </Wrap>
  );
};

// --------------------------------------------------------------------------- //
// Researcher view
// --------------------------------------------------------------------------- //

const SubmitForm = ({ program, onSubmitted }) => {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [severity, setSeverity] = useState('medium');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await createSubmission({
        program: program.id,
        title: title.trim(),
        description: description.trim(),
        severity_claimed: severity,
      });
      setTitle(''); setDescription(''); setSeverity('medium'); setOpen(false);
      onSubmitted();
    } catch {
      setError('Could not file the report. The program may no longer be active.');
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return <Button $primary type="button" onClick={() => setOpen(true)}>File a report</Button>;
  }
  return (
    <div style={{ marginTop: 12 }}>
      <Field htmlFor={`st-${program.id}`}>Report title</Field>
      <Input id={`st-${program.id}`} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="IDOR on vault export" />
      <Field htmlFor={`sd-${program.id}`}>Description (steps to reproduce)</Field>
      <TextArea id={`sd-${program.id}`} value={description} onChange={(e) => setDescription(e.target.value)} />
      <Field htmlFor={`ss-${program.id}`}>Claimed severity</Field>
      <Select id={`ss-${program.id}`} value={severity} onChange={(e) => setSeverity(e.target.value)}>
        {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
      </Select>
      {error && <Alert>{error}</Alert>}
      <ActionBar>
        <Button $primary type="button" disabled={busy || !title.trim() || !description.trim()} onClick={submit}>
          {busy ? 'Submitting…' : 'Submit report'}
        </Button>
        <Button type="button" disabled={busy} onClick={() => setOpen(false)}>Cancel</Button>
      </ActionBar>
    </div>
  );
};

const ResearchView = () => {
  const [programs, setPrograms] = useState([]);
  const [mySubmissions, setMySubmissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const [progs, subs] = await Promise.all([getAvailablePrograms(), getSubmissions()]);
      setPrograms(progs.results || progs);
      setMySubmissions(subs.results || subs);
    } catch {
      setError('Could not load available programs.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <Muted>Loading programs…</Muted>;

  return (
    <Wrap>
      <Muted style={{ marginBottom: 16 }}>
        Browse active programs and file reports against the app&apos;s defined attack surface. You
        never get access to anyone&apos;s vault data — only the in-scope APIs/auth.
      </Muted>
      {error && <Alert>{error}</Alert>}

      {programs.length === 0 ? (
        <Empty>No active programs right now.</Empty>
      ) : (
        programs.map((program) => (
          <Card key={program.id}>
            <Row>
              <Title>{program.title}</Title>
              <Muted style={{ margin: 0 }}>by {program.owner_username}</Muted>
            </Row>
            {program.scope?.length > 0 && <Muted>Scope: {program.scope.join(', ')}</Muted>}
            {program.policy && <Muted>{program.policy}</Muted>}
            {program.reward_tiers && Object.keys(program.reward_tiers).length > 0 && (
              <Muted>
                Rewards:{' '}
                {Object.entries(program.reward_tiers)
                  .map(([sev, amt]) => `${sev}: $${amt}`)
                  .join(' · ')}
              </Muted>
            )}
            <div style={{ marginTop: 10 }}>
              <SubmitForm program={program} onSubmitted={load} />
            </div>
          </Card>
        ))
      )}

      <Title style={{ marginTop: 24 }}>My submissions</Title>
      {mySubmissions.length === 0 ? (
        <Empty>You haven&apos;t filed any reports yet.</Empty>
      ) : (
        mySubmissions.map((s) => (
          <Card key={s.id}>
            <Row>
              <Title>{s.title}</Title>
              <StatusBadge status={s.status} kind="submission" />
            </Row>
            <Muted>{s.program_title}</Muted>
            {s.reward && (
              <Muted>
                Reward: {s.reward.amount} {s.reward.currency} (<StatusBadge status={s.reward.status} kind="reward" />)
              </Muted>
            )}
          </Card>
        ))
      )}
    </Wrap>
  );
};

// --------------------------------------------------------------------------- //
// Panel
// --------------------------------------------------------------------------- //

const BountyPrograms = () => {
  const [view, setView] = useState('owner');
  return (
    <Wrap>
      <SubTabs role="tablist">
        <SubTab
          type="button"
          role="tab"
          id="bp-subtab-owner"
          aria-controls="bp-subpanel"
          aria-selected={view === 'owner'}
          $active={view === 'owner'}
          onClick={() => setView('owner')}
        >
          My programs
        </SubTab>
        <SubTab
          type="button"
          role="tab"
          id="bp-subtab-research"
          aria-controls="bp-subpanel"
          aria-selected={view === 'research'}
          $active={view === 'research'}
          onClick={() => setView('research')}
        >
          Research &amp; submit
        </SubTab>
      </SubTabs>
      <div
        role="tabpanel"
        id="bp-subpanel"
        aria-labelledby={view === 'owner' ? 'bp-subtab-owner' : 'bp-subtab-research'}
      >
        {view === 'owner' ? <OwnerView /> : <ResearchView />}
      </div>
    </Wrap>
  );
};

export default BountyPrograms;
