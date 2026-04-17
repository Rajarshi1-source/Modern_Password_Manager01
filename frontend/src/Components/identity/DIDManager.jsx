import React, { useEffect, useState } from 'react';
import styled from 'styled-components';
import didService, { generateDidKey } from '../../services/didService';
import {
  deleteDid,
  exportWallet,
  importWallet,
  listDids,
  saveDid,
} from '../../services/credentialWalletStorage';

const Wrap = styled.div`
  max-width: 760px;
  margin: 2rem auto;
  padding: 2rem;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 18px rgba(0,0,0,0.06);
`;

const Btn = styled.button`
  background: ${({ $secondary, $danger }) =>
    $danger ? '#dc2626' : $secondary ? '#edeff2' : '#0f172a'};
  color: ${({ $secondary }) => ($secondary ? '#111' : '#fff')};
  padding: 0.45rem 0.8rem;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  margin-right: 0.4rem;
`;

const Code = styled.code`
  font-family: 'SF Mono', 'Fira Code', monospace;
  background: #f8fafc;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  word-break: break-all;
`;

const Row = styled.div`
  padding: 0.75rem 0;
  border-bottom: 1px solid #e2e8f0;
`;

const Warn = styled.div`
  background: #fef3c7;
  border: 1px solid #fbbf24;
  padding: 0.75rem 1rem;
  border-radius: 6px;
  margin: 1rem 0;
  color: #78350f;
`;

export default function DIDManager() {
  const [dids, setDids] = useState([]);
  const [newlyCreated, setNewlyCreated] = useState(null);
  const [serverDids, setServerDids] = useState([]);
  const [err, setErr] = useState('');

  const refresh = async () => {
    setDids(await listDids());
    try {
      setServerDids(await didService.listMyDids());
    } catch (e) {
      // Unauthenticated users just see empty server list.
    }
  };

  useEffect(() => { refresh(); }, []);

  const createDid = async () => {
    setErr('');
    try {
      const gen = generateDidKey();
      await saveDid({
        did: gen.did,
        multibase: gen.multibase,
        privateKeyHex: gen.privateKeyHex,
        publicKeyHex: gen.publicKeyHex,
        createdAt: new Date().toISOString(),
      });
      try {
        await didService.registerDid(gen.did, gen.multibase, true);
      } catch (e) {
        // Server registration optional; wallet still usable offline.
      }
      setNewlyCreated(gen);
      await refresh();
    } catch (e) {
      setErr(e.message || 'Failed to create DID');
    }
  };

  const remove = async (did) => {
    await deleteDid(did);
    await refresh();
  };

  const exportJSON = async () => {
    const blob = await exportWallet();
    const url = URL.createObjectURL(new Blob([JSON.stringify(blob, null, 2)], { type: 'application/json' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = `did-wallet-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const importJSON = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const txt = await file.text();
    await importWallet(JSON.parse(txt));
    await refresh();
  };

  return (
    <Wrap>
      <h2>Decentralized Identity</h2>
      <p>
        Generate and manage <Code>did:key</Code> identifiers whose private keys
        never leave your browser. Back the wallet up regularly - losing the
        private key means losing access to credentials issued to that DID.
      </p>

      <Row>
        <Btn onClick={createDid}>Create new DID</Btn>
        <Btn $secondary onClick={exportJSON}>Export wallet</Btn>
        <label style={{ display: 'inline-block' }}>
          <Btn as="span" $secondary>Import wallet</Btn>
          <input type="file" accept="application/json" onChange={importJSON} style={{ display: 'none' }} />
        </label>
      </Row>

      {newlyCreated && (
        <Warn>
          <div><strong>Back this up now.</strong> The private key below is
          shown only once.</div>
          <div style={{ marginTop: 6 }}>DID: <Code>{newlyCreated.did}</Code></div>
          <div>Private key: <Code>{newlyCreated.privateKeyHex}</Code></div>
          <Btn onClick={() => setNewlyCreated(null)} style={{ marginTop: 6 }}>I saved it</Btn>
        </Warn>
      )}

      <h3 style={{ marginTop: '1.25rem' }}>Local wallet DIDs</h3>
      {dids.length === 0 && <div>No DIDs yet.</div>}
      {dids.map((d) => (
        <Row key={d.did}>
          <div><Code>{d.did}</Code></div>
          <div style={{ marginTop: 4 }}>
            Created {new Date(d.createdAt).toLocaleString()}
          </div>
          <Btn $danger onClick={() => remove(d.did)} style={{ marginTop: 6 }}>Remove</Btn>
        </Row>
      ))}

      <h3 style={{ marginTop: '1.25rem' }}>Server-side registrations</h3>
      {serverDids.length === 0 && <div>None registered yet.</div>}
      {serverDids.map((d) => (
        <Row key={d.id}>
          <div><Code>{d.did_string}</Code> — {d.is_primary ? 'primary' : 'secondary'}</div>
        </Row>
      ))}

      {err && <div style={{ color: '#b91c1c', marginTop: '1rem' }}>{err}</div>}
    </Wrap>
  );
}
