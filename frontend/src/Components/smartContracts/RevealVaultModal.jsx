/**
 * RevealVaultModal
 * =================
 *
 * Orchestrates the hybrid reveal flow:
 *   1. POST /reveal/  -> returns ciphertext + pending-tx signal
 *   2. Poll /receipt/ until the on-chain anchor confirms (or times out)
 *
 * The plaintext is assumed to be decrypted client-side by the caller.
 * This component is only responsible for the one-shot UX: show the
 * encrypted payload, the tx hash as a link, and a live receipt badge.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import smartContractService from '../../services/smartContractService';

const POLL_INTERVAL_MS = 4000;
const MAX_POLLS = 30;

const RevealVaultModal = ({ vaultId, onClose, onRevealed }) => {
  const [state, setState] = useState({
    stage: 'idle', // 'idle' | 'revealing' | 'revealed' | 'error'
    payload: null,
    error: null,
    receipt: null,
  });
  const pollCount = useRef(0);
  const pollHandle = useRef(null);

  const reveal = useCallback(async () => {
    setState((s) => ({ ...s, stage: 'revealing', error: null }));
    try {
      const res = await smartContractService.revealVault(vaultId);
      if (!res.data?.unlocked) {
        setState({
          stage: 'error',
          error: res.data?.reason || 'Conditions not met',
          payload: null,
          receipt: null,
        });
        return;
      }
      setState((s) => ({
        ...s,
        stage: 'revealed',
        payload: res.data,
        receipt: {
          tx_hash: res.data.released_tx_hash || '',
          confirmed: false,
          pending: !!res.data.tx_hash_pending,
        },
      }));
      if (onRevealed) onRevealed(res.data);
    } catch (err) {
      setState({
        stage: 'error',
        error: err.response?.data?.error || err.message || 'Reveal failed',
        payload: null,
        receipt: null,
      });
    }
  }, [vaultId, onRevealed]);

  // Poll for receipt while pending.
  useEffect(() => {
    if (state.stage !== 'revealed') return undefined;
    if (!state.receipt?.pending) return undefined;

    const poll = async () => {
      pollCount.current += 1;
      try {
        const res = await smartContractService.getReceipt(vaultId);
        if (res.data?.confirmed) {
          setState((s) => ({
            ...s,
            receipt: {
              tx_hash: res.data.tx_hash,
              confirmed: true,
              pending: false,
              explorer_url: res.data.explorer_url,
            },
          }));
          return;
        }
        if (pollCount.current < MAX_POLLS) {
          pollHandle.current = setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch (_err) {
        // Swallow; the next poll tick will retry.
        if (pollCount.current < MAX_POLLS) {
          pollHandle.current = setTimeout(poll, POLL_INTERVAL_MS);
        }
      }
    };
    pollHandle.current = setTimeout(poll, POLL_INTERVAL_MS);
    return () => {
      if (pollHandle.current) clearTimeout(pollHandle.current);
    };
  }, [state.stage, state.receipt, vaultId]);

  return (
    <div className="reveal-modal-overlay" onClick={onClose}>
      <div className="reveal-modal" onClick={(e) => e.stopPropagation()}>
        <h3>Reveal Vault Password</h3>
        {state.stage === 'idle' && (
          <>
            <p>
              Revealing will evaluate conditions, decrypt the payload to
              your browser, and anchor an audit event on Arbitrum.
            </p>
            <button type="button" onClick={reveal}>Reveal</button>
            <button type="button" onClick={onClose}>Cancel</button>
          </>
        )}
        {state.stage === 'revealing' && <p>Evaluating conditions…</p>}
        {state.stage === 'revealed' && (
          <div>
            <p>Ciphertext delivered to this browser.</p>
            {state.receipt?.tx_hash ? (
              <p>
                Audit anchor:&nbsp;
                <code>{state.receipt.tx_hash.slice(0, 18)}…</code>
                &nbsp;
                {state.receipt.confirmed ? (
                  <span className="receipt-badge confirmed">confirmed</span>
                ) : (
                  <span className="receipt-badge pending">pending</span>
                )}
                {state.receipt.explorer_url && (
                  <>
                    &nbsp;
                    <a
                      href={state.receipt.explorer_url}
                      target="_blank"
                      rel="noreferrer noopener"
                    >view on Arbiscan</a>
                  </>
                )}
              </p>
            ) : (
              <p><em>On-chain anchor not submitted (feature flag off).</em></p>
            )}
            <button type="button" onClick={onClose}>Close</button>
          </div>
        )}
        {state.stage === 'error' && (
          <div>
            <p className="reveal-error">Error: {state.error}</p>
            <button type="button" onClick={onClose}>Close</button>
          </div>
        )}
      </div>
    </div>
  );
};

export default RevealVaultModal;
