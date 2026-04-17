import React, { useEffect, useState } from 'react';
import styled from 'styled-components';
import QRCode from 'qrcode.react';
import circadianTotpService from '../../services/circadianTotpService';

const Container = styled.div`
  max-width: 560px;
  margin: 2rem auto;
  padding: 2rem;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.08);
`;

const Title = styled.h2`
  font-size: 1.5rem;
  margin-bottom: 0.5rem;
`;

const Subtitle = styled.p`
  color: #555;
  margin-bottom: 1.5rem;
  font-size: 0.95rem;
`;

const Row = styled.div`
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
`;

const Button = styled.button`
  background: ${({ $secondary }) => ($secondary ? '#edeff2' : '#2563eb')};
  color: ${({ $secondary }) => ($secondary ? '#111' : '#fff')};
  border: none;
  border-radius: 8px;
  padding: 0.6rem 1rem;
  font-weight: 600;
  cursor: pointer;
  &:disabled { opacity: 0.5; cursor: not-allowed; }
`;

const Input = styled.input`
  padding: 0.55rem 0.75rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  font-size: 1rem;
  width: 160px;
`;

const ProfileBox = styled.div`
  margin-top: 1.5rem;
  padding: 1rem;
  background: #f8fafc;
  border-radius: 8px;
  font-size: 0.9rem;
  line-height: 1.5;
`;

const ErrorText = styled.div`
  color: #b91c1c;
  margin-top: 0.5rem;
`;

const SuccessText = styled.div`
  color: #166534;
  margin-top: 0.5rem;
`;

const minutesToClock = (m) => {
  const hh = String(Math.floor(m / 60) % 24).padStart(2, '0');
  const mm = String(m % 60).padStart(2, '0');
  return `${hh}:${mm} UTC`;
};

export default function CircadianTOTPSetup({ onComplete }) {
  const [profile, setProfile] = useState(null);
  const [device, setDevice] = useState(null);
  const [provisioningUri, setProvisioningUri] = useState('');
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [ok, setOk] = useState('');

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await circadianTotpService.getProfile();
      setProfile(data.profile);
      if (data.devices && data.devices.length > 0) {
        setDevice(data.devices[0]);
      }
    } catch (e) {
      setErr(e.response?.data?.error || 'Failed to load circadian profile');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const handleSetup = async () => {
    setErr(''); setOk('');
    try {
      const data = await circadianTotpService.setupDevice();
      setDevice(data.device);
      setProvisioningUri(data.provisioning_uri);
    } catch (e) {
      setErr(e.response?.data?.error || 'Failed to provision device');
    }
  };

  const handleVerify = async () => {
    setErr(''); setOk('');
    if (!device) return;
    try {
      const data = await circadianTotpService.verifyDevice(device.id, code);
      if (data.confirmed) {
        setOk('Circadian TOTP device confirmed.');
        setDevice(data.device);
        if (onComplete) onComplete(data.device);
      } else {
        setErr('Code did not match. Make sure your biological phase is calibrated.');
      }
    } catch (e) {
      setErr(e.response?.data?.error || 'Verification failed');
    }
  };

  const connectFitbit = async () => {
    setErr(''); setOk('');
    try {
      const data = await circadianTotpService.getWearableConnectUrl('fitbit');
      if (data.authorize_url) {
        window.location.href = data.authorize_url;
      }
    } catch (e) {
      setErr(e.response?.data?.error || 'Fitbit is not configured on the server');
    }
  };

  if (loading) return <Container>Loading circadian profile…</Container>;

  return (
    <Container>
      <Title>Biological Clock TOTP</Title>
      <Subtitle>
        Tie your one-time codes to your circadian rhythm. An attacker who
        merely steals the TOTP seed will still fail if their phase doesn&apos;t
        match your sleep pattern.
      </Subtitle>

      {profile && (
        <ProfileBox>
          <div>
            <strong>Chronotype:</strong> {profile.chronotype} &nbsp;·&nbsp;
            <strong>Baseline midpoint:</strong>{' '}
            {minutesToClock(profile.baseline_sleep_midpoint_minutes)}
          </div>
          <div>
            <strong>Phase lock window:</strong>{' '}
            ±{profile.phase_lock_minutes} minutes
          </div>
          <div>
            <strong>Samples:</strong> {profile.sample_count}
          </div>
        </ProfileBox>
      )}

      <Row style={{ marginTop: '1.5rem' }}>
        <Button onClick={connectFitbit}>Connect Fitbit</Button>
        {!device && <Button $secondary onClick={handleSetup}>Provision device</Button>}
      </Row>

      {device && !device.confirmed && provisioningUri && (
        <div style={{ marginTop: '1.5rem' }}>
          <Subtitle>
            Scan with any authenticator app as a bootstrap, then enter the current
            code below. Subsequent codes must match your biological phase.
          </Subtitle>
          <div style={{ background: '#f8fafc', padding: '1rem', borderRadius: 8, display: 'inline-block' }}>
            <QRCode value={provisioningUri} size={168} />
          </div>
          <Row style={{ marginTop: '1rem' }}>
            <Input
              value={code}
              onChange={(e) => setCode(e.target.value.trim())}
              placeholder="6-digit code"
              maxLength={6}
            />
            <Button onClick={handleVerify}>Verify</Button>
          </Row>
        </div>
      )}

      {device && device.confirmed && (
        <SuccessText>Circadian device is configured and confirmed.</SuccessText>
      )}

      {err && <ErrorText>{err}</ErrorText>}
      {ok && <SuccessText>{ok}</SuccessText>}
    </Container>
  );
}
