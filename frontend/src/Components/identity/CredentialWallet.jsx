import React, { useEffect, useState } from 'react';
import styled from 'styled-components';
import didService from '../../services/didService';
import {
  deleteCredential,
  listCredentials,
  saveCredential,
} from '../../services/credentialWalletStorage';

const Wrap = styled.div`
  max-width: 760px;
  margin: 2rem auto;
  padding: 2rem;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 18px rgba(0,0,0,0.06);
`;

const Card = styled.div`
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 0.75rem;
`;

const Tag = styled.span`
  display: inline-block;
  padding: 0.1rem 0.5rem;
  background: #e0e7ff;
  color: #3730a3;
  border-radius: 999px;
  font-size: 0.8rem;
  margin-left: 0.5rem;
`;

const Btn = styled.button`
  background: ${({ $danger }) => ($danger ? '#dc2626' : '#0f172a')};
  color: white;
  padding: 0.4rem 0.75rem;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  margin-right: 0.4rem;
`;

const Pre = styled.pre`
  background: #0f172a;
  color: #e2e8f0;
  padding: 0.75rem;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 0.8rem;
`;

export default function CredentialWallet() {
  const [local, setLocal] = useState([]);
  const [server, setServer] = useState([]);
  const [expanded, setExpanded] = useState({});
  const [err, setErr] = useState('');

  const refresh = async () => {
    setLocal(await listCredentials());
    try {
      setServer(await didService.listMyCredentials());
    } catch (e) {
      setErr('Log in to see server-side credentials.');
    }
  };

  useEffect(() => { refresh(); }, []);

  const saveFromServer = async (vc) => {
    await saveCredential(vc.id, vc.jwt_vc || '', vc.jsonld_vc || {});
    await refresh();
  };

  const remove = async (id) => {
    await deleteCredential(id);
    await refresh();
  };

  return (
    <Wrap>
      <h2>Credential wallet</h2>
      <p>Credentials issued to your DIDs. Save locally for offline disclosure.</p>

      <h3>Server-side</h3>
      {server.length === 0 && <div>No credentials on the server.</div>}
      {server.map((vc) => (
        <Card key={vc.id}>
          <div>
            <strong>{vc.schema || 'Credential'}</strong>
            <Tag>{vc.status}</Tag>
          </div>
          <div style={{ fontSize: '.85rem', color: '#475569' }}>
            issued {new Date(vc.issued_at).toLocaleString()} · subject{' '}
            <code>{vc.subject_did}</code>
          </div>
          <Btn onClick={() => saveFromServer(vc)} style={{ marginTop: 6 }}>Save locally</Btn>
        </Card>
      ))}

      <h3 style={{ marginTop: '1.25rem' }}>Local wallet</h3>
      {local.length === 0 && <div>Wallet is empty.</div>}
      {local.map((vc) => (
        <Card key={vc.id}>
          <div>
            <strong>{vc.jsonld?.type?.[1] || 'Credential'}</strong>
            <Btn
              $danger
              onClick={() => remove(vc.id)}
              style={{ float: 'right' }}
            >
              Remove
            </Btn>
            <Btn
              onClick={() =>
                setExpanded({ ...expanded, [vc.id]: !expanded[vc.id] })
              }
              style={{ float: 'right' }}
            >
              {expanded[vc.id] ? 'Hide' : 'Show'} JSON-LD
            </Btn>
          </div>
          <div style={{ fontSize: '.85rem', color: '#475569' }}>
            Saved {new Date(vc.savedAt).toLocaleString()}
          </div>
          {expanded[vc.id] && <Pre>{JSON.stringify(vc.jsonld, null, 2)}</Pre>}
        </Card>
      ))}

      {err && <div style={{ color: '#64748b', marginTop: '1rem' }}>{err}</div>}
    </Wrap>
  );
}
