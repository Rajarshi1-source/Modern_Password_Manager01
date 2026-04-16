/**
 * SealedAutofillFrame — sandboxed iframe that holds a decrypted
 * shared password just long enough for the user to drop it into a
 * form on the target site.
 *
 * Why an iframe:
 *   - The parent page (this dashboard) never reads the plaintext off
 *     of a DOM element it owns; the value lives in a srcdoc iframe
 *     with `sandbox="allow-scripts"` and no `allow-same-origin`.
 *   - The iframe exposes ONE operation via postMessage: "copy to
 *     clipboard" — which is user-initiated (click) and immediately
 *     schedules a clear.
 *   - When the user dismisses the frame, we overwrite the srcdoc with
 *     an empty document and best-effort zero the in-memory string.
 *
 * This is strictly a web-fallback when the browser extension is not
 * installed. The extension path is preferred because it can inject
 * the plaintext directly into the real form field on the target site.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import styled from 'styled-components';
import { X, Copy, Shield, ExternalLink, Clock } from 'lucide-react';

const Wrapper = styled.div`
  border: 1px solid rgba(74, 108, 247, 0.2);
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(74, 108, 247, 0.04), rgba(124, 58, 237, 0.04));
  padding: 1rem 1.25rem;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
  font-size: 0.9rem;
`;

const FrameHost = styled.iframe`
  width: 100%;
  height: 78px;
  border: 1px solid var(--border, #eee);
  border-radius: 10px;
  background: white;
`;

const Footer = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-top: 0.75rem;
  font-size: 0.78rem;
  color: var(--text-secondary, #888);
`;

const Button = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.8rem;
  border-radius: 8px;
  border: 1px solid var(--border, #ddd);
  background: white;
  color: var(--text-primary, #333);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s;

  &:hover {
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    transform: translateY(-1px);
  }
`;

function htmlEscape(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function buildSrcDoc(password, nonce) {
  // The srcdoc runs inside a sandboxed iframe WITHOUT
  // `allow-same-origin`, so even though it is same-origin by URL
  // it is treated as a unique opaque origin and cannot read any
  // parent state. It exposes `{type: 'copy', nonce}` as the only
  // message it will respond to.
  const safePw = htmlEscape(password);
  const safeNonce = htmlEscape(nonce);
  return `<!doctype html><html><head><meta charset="utf-8"><style>
    body { margin: 0; font-family: system-ui, sans-serif; font-size: 13px; }
    .pw-field { width: 100%; padding: 8px 10px; border: 1px solid #ddd; border-radius: 8px; background: #fff; color: #333; letter-spacing: 2px; box-sizing: border-box; }
  </style></head><body>
    <input id="pw" class="pw-field" type="password" readonly value="${safePw}" />
    <script>
      (function(){
        var pw = document.getElementById('pw');
        var used = false;
        function zero(){ try { pw.value = ''; } catch(_){} }
        window.addEventListener('message', function(ev){
          var d = ev.data || {};
          if (d.nonce !== '${safeNonce}') return;
          if (used) return;
          if (d.type === 'copy') {
            used = true;
            try {
              pw.type = 'text';
              pw.select();
              document.execCommand('copy');
            } catch(_){}
            setTimeout(zero, 100);
            parent.postMessage({ type: 'fhe_share:iframe_copied', nonce: '${safeNonce}' }, '*');
          } else if (d.type === 'reveal') {
            pw.type = 'text';
          } else if (d.type === 'hide') {
            pw.type = 'password';
          } else if (d.type === 'destroy') {
            used = true;
            zero();
          }
        });
      })();
    </script>
  </body></html>`;
}

export default function SealedAutofillFrame({ domain, password, tokenMetadata, onDismiss }) {
  const iframeRef = useRef(null);
  const nonce = useMemo(() => {
    const arr = new Uint8Array(16);
    (window.crypto || window.msCrypto).getRandomValues(arr);
    return Array.from(arr).map((b) => b.toString(16).padStart(2, '0')).join('');
  }, []);
  const srcDoc = useMemo(() => buildSrcDoc(password || '', nonce), [password, nonce]);
  const [copied, setCopied] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(30);

  useEffect(() => {
    const onMsg = (ev) => {
      const d = ev.data;
      if (!d || d.nonce !== nonce) return;
      if (d.type === 'fhe_share:iframe_copied') {
        setCopied(true);
        try {
          setTimeout(() => navigator.clipboard.writeText(''), 20_000);
        } catch (_err) {
          // clipboard clear is best-effort
        }
      }
    };
    window.addEventListener('message', onMsg);
    return () => window.removeEventListener('message', onMsg);
  }, [nonce]);

  useEffect(() => {
    if (secondsLeft <= 0) {
      onDismiss?.();
      return undefined;
    }
    const t = setTimeout(() => setSecondsLeft((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [secondsLeft, onDismiss]);

  const doCopy = () => {
    iframeRef.current?.contentWindow?.postMessage({ type: 'copy', nonce }, '*');
  };
  const openSite = () => {
    const url = domain?.startsWith('http') ? domain : `https://${domain}`;
    window.open(url, '_blank', 'noopener,noreferrer');
  };
  const dismiss = () => {
    iframeRef.current?.contentWindow?.postMessage({ type: 'destroy', nonce }, '*');
    onDismiss?.();
  };

  return (
    <Wrapper>
      <Header>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
          <Shield size={14} /> Sealed autofill frame (web fallback)
        </span>
        <Button type="button" onClick={dismiss}>
          <X size={14} /> Close
        </Button>
      </Header>
      <FrameHost
        ref={iframeRef}
        title={`sealed-autofill-${domain}`}
        sandbox="allow-scripts"
        srcDoc={srcDoc}
      />
      <Footer>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
          <Clock size={12} /> Auto-closes in {secondsLeft}s
          {copied && ' · clipboard will be cleared in ~20s'}
          {tokenMetadata?.strength_class && ` · strength: ${tokenMetadata.strength_class}`}
        </span>
        <div style={{ display: 'inline-flex', gap: '0.4rem' }}>
          <Button type="button" onClick={doCopy}>
            <Copy size={14} /> {copied ? 'Copied' : 'Copy once'}
          </Button>
          <Button type="button" onClick={openSite}>
            <ExternalLink size={14} /> Open {domain}
          </Button>
        </div>
      </Footer>
    </Wrapper>
  );
}
