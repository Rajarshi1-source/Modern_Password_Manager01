/**
 * Bug Bounty — Vault Self-Pentest Dashboard (Phase 1)
 * ===================================================
 *
 * Shows the result of the continuous, non-destructive self-pentest: a severity
 * summary, a "Run self-test" trigger, and the list of open findings with
 * remediation and triage actions (acknowledge / resolve / false-positive).
 *
 * Read-only posture data — no plaintext secrets are ever returned by the API.
 */

import React, { useCallback, useEffect, useState } from 'react';
import styled from 'styled-components';
import { motion } from 'framer-motion';
import { FaShieldAlt, FaPlay, FaCheck, FaEyeSlash, FaRegBell } from 'react-icons/fa';
import { getSelfTest, runSelfTest, updateFindingStatus } from '../../services/bugBountyService';

const SEVERITY = {
  critical: { color: '#dc2626', label: 'Critical' },
  high: { color: '#ef4444', label: 'High' },
  medium: { color: '#f59e0b', label: 'Medium' },
  low: { color: '#3b82f6', label: 'Low' },
  info: { color: '#6b7280', label: 'Info' },
};

const Page = styled.div`
  max-width: 860px;
  margin: 0 auto;
  padding: 24px 16px 48px;
`;

const Header = styled.header`
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;

  h1 { font-size: 22px; margin: 0 0 6px; }
  p { margin: 0; color: ${(p) => p.theme.textSecondary || '#9ca3af'}; max-width: 540px; line-height: 1.5; }
`;

const RunButton = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: none;
  border-radius: 8px;
  padding: 10px 18px;
  font-weight: 600;
  cursor: pointer;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #fff;
  &:disabled { opacity: 0.6; cursor: not-allowed; }
`;

const SummaryBar = styled.div`
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 20px;
`;

const Pill = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  padding: 6px 12px;
  border-radius: 999px;
  color: #fff;
  background: ${(p) => p.$color};
`;

const FindingCard = styled(motion.div)`
  border: 1px solid ${(p) => p.theme.borderColor || 'rgba(127,127,127,0.25)'};
  border-left: 4px solid ${(p) => p.$color};
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 12px;
  background: ${(p) => p.theme.cardBg || 'transparent'};
`;

const FindingHead = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
`;

const Title = styled.h3`
  font-size: 15px;
  margin: 0;
`;

const SevTag = styled.span`
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: ${(p) => p.$color};
`;

const Remediation = styled.p`
  margin: 8px 0 0;
  font-size: 14px;
  color: ${(p) => p.theme.textSecondary || '#9ca3af'};
  line-height: 1.5;
`;

const StatusRow = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
`;

const Action = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  border: 1px solid ${(p) => p.theme.borderColor || 'rgba(127,127,127,0.3)'};
  background: transparent;
  color: ${(p) => p.theme.textSecondary || '#9ca3af'};
  border-radius: 6px;
  padding: 5px 10px;
  cursor: pointer;
  &:disabled { opacity: 0.5; cursor: default; }
`;

const Muted = styled.p`
  color: ${(p) => p.theme.textSecondary || '#9ca3af'};
  font-size: 14px;
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 40px 16px;
  color: ${(p) => p.theme.textSecondary || '#9ca3af'};
`;

const BugBountyDashboard = () => {
  const [run, setRun] = useState(null);
  const [findings, setFindings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const data = await getSelfTest();
      setRun(data.latest_run);
      setFindings(data.findings || []);
    } catch {
      setError('Could not load self-pentest results.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRun = async () => {
    setRunning(true);
    setError(null);
    try {
      const data = await runSelfTest();
      setRun(data.latest_run);
      setFindings(data.findings || []);
    } catch {
      setError('Self-test failed to run. Please try again later.');
    } finally {
      setRunning(false);
    }
  };

  const setStatus = async (finding, status) => {
    try {
      await updateFindingStatus(finding.id, status);
      // Acknowledged stays visible; resolved/false-positive drop off the list.
      setFindings((prev) =>
        status === 'acknowledged'
          ? prev.map((f) => (f.id === finding.id ? { ...f, status } : f))
          : prev.filter((f) => f.id !== finding.id),
      );
    } catch {
      setError('Could not update the finding.');
    }
  };

  // Derive the pill counts from the live open-findings list so they stay in
  // sync with triage actions (and a load failure) without a reload.
  const counts = findings.reduce((acc, f) => {
    acc[f.severity] = (acc[f.severity] || 0) + 1;
    return acc;
  }, {});

  return (
    <Page>
      <Header>
        <div>
          <h1><FaShieldAlt aria-hidden="true" /> Bug Bounty — Vault Self-Pentest</h1>
          <p>
            A continuous, non-destructive self-assessment of your account&apos;s security posture.
            It aggregates existing signals (breaches, 2FA, weak passwords) into prioritised findings
            with remediation — computed server-side from metadata only, never your passwords.
          </p>
        </div>
        <RunButton type="button" onClick={handleRun} disabled={running || loading}>
          <FaPlay aria-hidden="true" /> {running ? 'Running…' : 'Run self-test'}
        </RunButton>
      </Header>

      {error && <Muted role="alert">⚠️ {error}</Muted>}

      {!loading && (
        <SummaryBar>
          {['critical', 'high', 'medium', 'low', 'info'].map((sev) => (
            (counts[sev] || 0) > 0 ? (
              <Pill key={sev} $color={SEVERITY[sev].color}>
                {counts[sev]} {SEVERITY[sev].label}
              </Pill>
            ) : null
          ))}
          {run?.started_at && (
            <Muted style={{ alignSelf: 'center', margin: 0 }}>
              Last run: {new Date(run.started_at).toLocaleString()}
            </Muted>
          )}
        </SummaryBar>
      )}

      {loading ? (
        <Muted>Loading self-pentest results…</Muted>
      ) : error && !run && findings.length === 0 ? (
        <EmptyState>
          <p style={{ fontSize: 32, margin: 0 }}>⚠️</p>
          <p>We couldn&apos;t load your current self-test state. Please try again.</p>
        </EmptyState>
      ) : findings.length === 0 ? (
        <EmptyState>
          <p style={{ fontSize: 32, margin: 0 }}>✅</p>
          <p>No open findings. {run ? 'Your posture looks clean.' : 'Run a self-test to begin.'}</p>
        </EmptyState>
      ) : (
        findings.map((f) => {
          const sev = SEVERITY[f.severity] || SEVERITY.info;
          return (
            <FindingCard
              key={f.id}
              $color={sev.color}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <FindingHead>
                <Title>{f.title}</Title>
                <SevTag $color={sev.color}>{sev.label}</SevTag>
              </FindingHead>
              {f.remediation && <Remediation>{f.remediation}</Remediation>}
              <StatusRow>
                <Action
                  type="button"
                  onClick={() => setStatus(f, 'acknowledged')}
                  disabled={f.status === 'acknowledged'}
                >
                  <FaRegBell aria-hidden="true" /> Acknowledge
                </Action>
                <Action type="button" onClick={() => setStatus(f, 'resolved')}>
                  <FaCheck aria-hidden="true" /> Mark resolved
                </Action>
                <Action type="button" onClick={() => setStatus(f, 'false_positive')}>
                  <FaEyeSlash aria-hidden="true" /> False positive
                </Action>
              </StatusRow>
            </FindingCard>
          );
        })
      )}
    </Page>
  );
};

export default BugBountyDashboard;
