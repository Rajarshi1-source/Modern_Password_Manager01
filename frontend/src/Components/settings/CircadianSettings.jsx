import React, { useEffect, useState } from 'react';
import styled from 'styled-components';
import circadianTotpService from '../../services/circadianTotpService';
import CircadianTOTPSetup from '../auth/CircadianTOTPSetup';

const Wrap = styled.div`
  max-width: 760px;
  margin: 2rem auto;
  padding: 2rem;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 18px rgba(0,0,0,0.06);
`;

const Title = styled.h2`
  margin: 0 0 0.5rem;
`;

const Sub = styled.p`
  color: #475569;
  margin-bottom: 1.5rem;
`;

const Row = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 0;
  border-bottom: 1px solid #e2e8f0;
`;

const Muted = styled.span`
  color: #64748b;
  font-size: 0.9rem;
`;

const Btn = styled.button`
  background: ${({ $danger }) => ($danger ? '#dc2626' : '#0f172a')};
  color: white;
  border: none;
  border-radius: 6px;
  padding: 0.4rem 0.75rem;
  cursor: pointer;
  font-size: 0.9rem;
`;

const PROVIDERS = ['fitbit', 'apple_health', 'oura', 'google_fit', 'manual'];

export default function CircadianSettings() {
  const [data, setData] = useState({ profile: null, wearables: [], devices: [] });
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const refresh = async () => {
    setLoading(true);
    try {
      setData(await circadianTotpService.getProfile());
    } catch (e) {
      setErr(e.response?.data?.error || 'Failed to load circadian data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  const connect = async (provider) => {
    try {
      const { authorize_url } = await circadianTotpService.getWearableConnectUrl(provider);
      if (authorize_url) window.location.href = authorize_url;
    } catch (e) {
      setErr(e.response?.data?.error || `Cannot connect ${provider}`);
    }
  };

  const unlink = async (provider) => {
    await circadianTotpService.unlinkWearable(provider);
    refresh();
  };

  const recompute = async () => {
    await circadianTotpService.recomputeCalibration();
    refresh();
  };

  if (loading) return <Wrap>Loading…</Wrap>;

  return (
    <Wrap>
      <Title>Circadian TOTP settings</Title>
      <Sub>
        Manage linked wearables, recalibrate your biological phase, and register
        new authenticator devices.
      </Sub>

      <h3>Linked wearables</h3>
      {PROVIDERS.map((p) => {
        const linked = (data.wearables || []).find((w) => w.provider === p);
        return (
          <Row key={p}>
            <div>
              <strong>{p.replace('_', ' ')}</strong>{' '}
              <Muted>
                {linked ? `linked${linked.last_synced_at ? ' · last sync ' + new Date(linked.last_synced_at).toLocaleString() : ''}` : 'not linked'}
              </Muted>
            </div>
            <div>
              {linked ? (
                <Btn $danger onClick={() => unlink(p)}>Unlink</Btn>
              ) : (
                <Btn onClick={() => connect(p)}>Connect</Btn>
              )}
            </div>
          </Row>
        );
      })}

      <Row style={{ marginTop: '1.5rem', borderBottom: 'none' }}>
        <Btn onClick={recompute}>Recompute calibration now</Btn>
      </Row>

      <CircadianTOTPSetup onComplete={refresh} />

      {err && <div style={{ color: '#b91c1c', marginTop: '1rem' }}>{err}</div>}
    </Wrap>
  );
}
