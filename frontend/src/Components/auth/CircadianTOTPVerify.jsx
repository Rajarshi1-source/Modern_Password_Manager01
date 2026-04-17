import React, { useState } from 'react';
import styled from 'styled-components';
import circadianTotpService from '../../services/circadianTotpService';

const Wrap = styled.div`
  max-width: 380px;
  margin: 1rem auto;
  padding: 1.25rem;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.07);
`;

const Label = styled.label`
  display: block;
  font-weight: 600;
  margin-bottom: 0.4rem;
`;

const Input = styled.input`
  width: 100%;
  padding: 0.55rem 0.75rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  font-size: 1.2rem;
  letter-spacing: 3px;
  text-align: center;
`;

const Button = styled.button`
  margin-top: 0.75rem;
  width: 100%;
  padding: 0.65rem;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  &:disabled { opacity: 0.6; }
`;

const HelperText = styled.p`
  font-size: 0.85rem;
  color: #475569;
  margin-top: 0.5rem;
`;

const ErrorText = styled.div`
  color: #b91c1c;
  margin-top: 0.5rem;
  font-size: 0.9rem;
`;

export default function CircadianTOTPVerify({ deviceId = null, onVerified }) {
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    setErr(''); setBusy(true);
    try {
      const res = await circadianTotpService.verifyCode(code, deviceId);
      if (res?.verified) {
        if (onVerified) onVerified();
      } else {
        setErr(res?.error || 'Code did not match your current biological phase.');
      }
    } catch (e2) {
      setErr(e2.response?.data?.error || 'Verification failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Wrap>
      <form onSubmit={submit}>
        <Label>Biological TOTP code</Label>
        <Input
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          placeholder="••••••"
          autoFocus
        />
        <HelperText>
          Your code is validated against a ±phase-lock window derived from your
          recent sleep midpoint.
        </HelperText>
        <Button disabled={busy || code.length !== 6} type="submit">
          {busy ? 'Verifying…' : 'Verify'}
        </Button>
        {err && <ErrorText>{err}</ErrorText>}
      </form>
    </Wrap>
  );
}
