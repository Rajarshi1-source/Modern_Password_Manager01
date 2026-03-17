import React, { useState, useCallback } from 'react';
import styled, { keyframes } from 'styled-components';
import {
  Shield, Globe, Clock, Hash, Lock, EyeOff,
  CheckCircle, AlertTriangle, Zap, ExternalLink
} from 'lucide-react';
import fheSharingService from '../../services/fhe/fheSharingService';

const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
`;

const glowPulse = keyframes`
  0%, 100% { box-shadow: 0 0 0 0 rgba(74, 108, 247, 0.15); }
  50% { box-shadow: 0 0 0 6px rgba(74, 108, 247, 0); }
`;

const Card = styled.div`
  background: white;
  border-radius: 14px;
  border: 1px solid var(--border, #eee);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  overflow: hidden;
  transition: all 0.25s ease;
  animation: ${fadeIn} 0.4s ease;

  &:hover {
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.1);
    transform: translateY(-2px);
    border-color: rgba(74, 108, 247, 0.2);
  }
`;

const CardHeader = styled.div`
  padding: 1.25rem 1.5rem;
  background: linear-gradient(135deg, rgba(74, 108, 247, 0.04), rgba(124, 58, 237, 0.04));
  border-bottom: 1px solid var(--border, #f0f0f0);
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const SharedBy = styled.div`
  display: flex;
  align-items: center;
  gap: 0.75rem;
`;

const ShareAvatar = styled.div`
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: linear-gradient(135deg, #4A6CF7, #7C3AED);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 700;
  font-size: 0.9rem;
  flex-shrink: 0;
`;

const SharerInfo = styled.div``;

const SharerName = styled.div`
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--text-primary, #1a1a1a);
`;

const SharerLabel = styled.div`
  font-size: 0.75rem;
  color: var(--text-secondary, #888);
  display: flex;
  align-items: center;
  gap: 0.25rem;
`;

const FHEBadge = styled.div`
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.3rem 0.65rem;
  background: linear-gradient(135deg, #4A6CF7, #7C3AED);
  color: white;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.03em;
`;

const CardBody = styled.div`
  padding: 1.25rem 1.5rem;
`;

const InfoRow = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  font-size: 0.85rem;
  color: var(--text-secondary, #666);

  svg { flex-shrink: 0; color: var(--text-muted, #aaa); }
  strong { color: var(--text-primary, #1a1a1a); font-weight: 600; }
`;

const DomainList = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.35rem;
`;

const DomainTag = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.2rem 0.55rem;
  background: rgba(74, 108, 247, 0.08);
  color: #4A6CF7;
  border-radius: 6px;
  font-size: 0.78rem;
  font-weight: 500;
`;

const Divider = styled.div`
  height: 1px;
  background: var(--border, #f0f0f0);
  margin: 1rem 0;
`;

const CardFooter = styled.div`
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border, #f0f0f0);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
`;

const AutofillButton = styled.button`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 1.25rem;
  background: linear-gradient(135deg, #4A6CF7, #6366F1);
  color: white;
  border: none;
  border-radius: 10px;
  font-weight: 600;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s;
  animation: ${glowPulse} 3s infinite;

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(74, 108, 247, 0.4);
  }

  &:active { transform: translateY(0); }

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
    transform: none;
    animation: none;
    box-shadow: none;
  }
`;

const StatusInfo = styled.div`
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  font-size: 0.78rem;
  color: var(--text-secondary, #888);
`;

const SuccessMessage = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 1rem;
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.15);
  border-radius: 8px;
  color: #059669;
  font-size: 0.8rem;
  font-weight: 500;
  margin-top: 0.75rem;
`;

const ErrorMessage = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 1rem;
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.15);
  border-radius: 8px;
  color: #B91C1C;
  font-size: 0.8rem;
  margin-top: 0.75rem;
`;


function AutofillTokenCard({ share, onUsed }) {
  const [autofilling, setAutofilling] = useState(false);
  const [autofillResult, setAutofillResult] = useState(null);
  const [error, setError] = useState(null);

  const domains = share.bound_domains || [];
  const isUsable = share.is_usable !== false;

  const handleAutofill = useCallback(async (domain) => {
    setAutofilling(true);
    setError(null);
    setAutofillResult(null);

    try {
      const result = await fheSharingService.useAutofillToken(share.id, domain);
      setAutofillResult({
        domain,
        useCount: result.use_count,
        remaining: result.remaining_uses,
      });
      if (onUsed) onUsed();
    } catch (err) {
      setError(err.error || 'Autofill failed');
    } finally {
      setAutofilling(false);
    }
  }, [share.id, onUsed]);

  const formatExpiry = () => {
    if (!share.expires_at) return 'No expiration';
    const date = new Date(share.expires_at);
    const now = new Date();
    const diffMs = date - now;
    if (diffMs < 0) return 'Expired';
    const hours = Math.floor(diffMs / 3600000);
    if (hours < 24) return `${hours}h remaining`;
    return `${Math.floor(hours / 24)}d remaining`;
  };

  return (
    <Card>
      <CardHeader>
        <SharedBy>
          <ShareAvatar>
            {(share.owner_username || '?')[0].toUpperCase()}
          </ShareAvatar>
          <SharerInfo>
            <SharerName>{share.owner_username}</SharerName>
            <SharerLabel>
              <EyeOff size={11} /> Shared password (hidden)
            </SharerLabel>
          </SharerInfo>
        </SharedBy>
        <FHEBadge>
          <Shield size={11} />
          FHE
        </FHEBadge>
      </CardHeader>

      <CardBody>
        <InfoRow>
          <Globe size={15} />
          <div>
            <strong>Domains: </strong>
            {domains.length > 0 ? (
              <DomainList>
                {domains.map(d => (
                  <DomainTag key={d}>
                    <Globe size={10} />
                    {d}
                  </DomainTag>
                ))}
              </DomainList>
            ) : (
              <span>Any domain</span>
            )}
          </div>
        </InfoRow>

        <InfoRow>
          <Lock size={15} />
          <span>Permission: <strong>Autofill only</strong> — you cannot view or copy this password</span>
        </InfoRow>

        <InfoRow>
          <Hash size={15} />
          <span>
            Used <strong>{share.use_count || 0}</strong> time{share.use_count !== 1 ? 's' : ''}
            {share.remaining_uses != null && ` (${share.remaining_uses} remaining)`}
          </span>
        </InfoRow>

        <InfoRow>
          <Clock size={15} />
          <span>{formatExpiry()}</span>
        </InfoRow>

        {autofillResult && (
          <SuccessMessage>
            <CheckCircle size={15} />
            Autofill data generated for <strong>{autofillResult.domain}</strong> (use #{autofillResult.useCount})
          </SuccessMessage>
        )}

        {error && (
          <ErrorMessage>
            <AlertTriangle size={15} />
            {error}
          </ErrorMessage>
        )}
      </CardBody>

      <CardFooter>
        <StatusInfo>
          <span>{isUsable ? '✅ Ready to autofill' : '⛔ Not available'}</span>
        </StatusInfo>

        {domains.length > 0 ? (
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {domains.map(domain => (
              <AutofillButton
                key={domain}
                disabled={!isUsable || autofilling}
                onClick={() => handleAutofill(domain)}
              >
                {autofilling ? (
                  <><Zap size={14} /> Filling...</>
                ) : (
                  <><ExternalLink size={14} /> {domain}</>
                )}
              </AutofillButton>
            ))}
          </div>
        ) : (
          <AutofillButton
            disabled={!isUsable || autofilling}
            onClick={() => handleAutofill(window.location.hostname)}
          >
            {autofilling ? (
              <><Zap size={14} /> Filling...</>
            ) : (
              <><Zap size={14} /> Autofill Now</>
            )}
          </AutofillButton>
        )}
      </CardFooter>
    </Card>
  );
}

export default AutofillTokenCard;
