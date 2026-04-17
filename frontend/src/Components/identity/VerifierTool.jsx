import React, { useState } from 'react';
import styled from 'styled-components';
import didService from '../../services/didService';

const Wrap = styled.div`
  max-width: 680px;
  margin: 2rem auto;
  padding: 2rem;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 18px rgba(0,0,0,0.06);
`;

const Area = styled.textarea`
  width: 100%;
  min-height: 160px;
  font-family: 'SF Mono', monospace;
  font-size: 0.85rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  padding: 0.6rem;
  margin-bottom: 1rem;
`;

const Input = styled.input`
  width: 100%;
  padding: 0.5rem;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
  margin-bottom: 0.75rem;
`;

const Btn = styled.button`
  background: #0f172a;
  color: white;
  padding: 0.6rem 1rem;
  border: none;
  border-radius: 8px;
  cursor: pointer;
`;

const Pre = styled.pre`
  background: #0f172a;
  color: #e2e8f0;
  padding: 0.75rem;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 0.8rem;
  margin-top: 1rem;
`;

export default function VerifierTool() {
  const [vp, setVp] = useState('');
  const [nonce, setNonce] = useState('');
  const [audience, setAudience] = useState('');
  const [res, setRes] = useState(null);
  const [err, setErr] = useState('');

  const verify = async () => {
    setErr(''); setRes(null);
    try {
      const data = await didService.verifyPresentation(vp, { nonce, audience });
      setRes(data);
    } catch (e) {
      setErr(e.response?.data?.error || e.message || 'Verification failed');
    }
  };

  return (
    <Wrap>
      <h2>Verify a Presentation</h2>
      <p>Paste a JWT Verifiable Presentation to check its signatures and contents.</p>
      <Area value={vp} onChange={(e) => setVp(e.target.value)} placeholder="eyJhbGciOi…" />
      <Input value={nonce} onChange={(e) => setNonce(e.target.value)} placeholder="Expected nonce (optional)" />
      <Input value={audience} onChange={(e) => setAudience(e.target.value)} placeholder="Expected audience (optional)" />
      <Btn onClick={verify}>Verify</Btn>
      {res && <Pre>{JSON.stringify(res, null, 2)}</Pre>}
      {err && <div style={{ color: '#b91c1c', marginTop: '.75rem' }}>{err}</div>}
    </Wrap>
  );
}
