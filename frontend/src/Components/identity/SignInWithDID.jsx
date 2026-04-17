import React, { useEffect, useState } from 'react';
import styled from 'styled-components';
import { useNavigate } from 'react-router-dom';
import didService, { signVp } from '../../services/didService';
import { listDids } from '../../services/credentialWalletStorage';

const Wrap = styled.div`
  max-width: 480px;
  margin: 3rem auto;
  padding: 2rem;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 18px rgba(0,0,0,0.06);
`;

const Select = styled.select`
  width: 100%;
  padding: 0.5rem;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
  margin-bottom: 1rem;
`;

const Btn = styled.button`
  width: 100%;
  padding: 0.7rem;
  background: #0f172a;
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
`;

const ErrorText = styled.div`
  color: #b91c1c;
  margin-top: 0.75rem;
  font-size: 0.9rem;
`;

const SuccessText = styled.div`
  color: #166534;
  margin-top: 0.75rem;
`;

export default function SignInWithDID() {
  const [dids, setDids] = useState([]);
  const [selected, setSelected] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [ok, setOk] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    listDids().then((list) => {
      setDids(list);
      if (list.length > 0) setSelected(list[0].did);
    });
  }, []);

  const signIn = async () => {
    setErr(''); setOk(''); setBusy(true);
    try {
      const entry = dids.find((d) => d.did === selected);
      if (!entry) throw new Error('Select a DID');
      const challenge = await didService.requestChallenge(entry.did);
      const vp = await signVp({
        holderDid: entry.did,
        privateKeyHex: entry.privateKeyHex,
        nonce: challenge.nonce,
      });
      const result = await didService.signInVerify({
        did: entry.did,
        nonce: challenge.nonce,
        vpJwt: vp,
      });
      if (result?.verified && result?.access_token) {
        localStorage.setItem('token', result.access_token);
        if (result.refresh_token) {
          localStorage.setItem('refresh_token', result.refresh_token);
        }
        setOk('Signed in. Redirecting…');
        setTimeout(() => navigate('/'), 500);
      } else {
        setErr((result?.errors || []).join(', ') || 'Verification failed');
      }
    } catch (e) {
      setErr(e.response?.data?.error || e.message || 'Sign-in failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Wrap>
      <h2>Sign in with DID</h2>
      <p style={{ color: '#475569' }}>
        Authenticate with a decentralized identifier. No password, no server-held
        secret.
      </p>
      {dids.length === 0 ? (
        <div>
          You don&apos;t have any local DIDs. Create one in{' '}
          <a href="/settings/identity">Identity settings</a>.
        </div>
      ) : (
        <>
          <Select value={selected} onChange={(e) => setSelected(e.target.value)}>
            {dids.map((d) => (
              <option key={d.did} value={d.did}>{d.did}</option>
            ))}
          </Select>
          <Btn onClick={signIn} disabled={busy}>
            {busy ? 'Signing…' : 'Sign in'}
          </Btn>
        </>
      )}
      {err && <ErrorText>{err}</ErrorText>}
      {ok && <SuccessText>{ok}</SuccessText>}
    </Wrap>
  );
}
