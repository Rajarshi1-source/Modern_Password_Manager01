import React, { useEffect, useState } from 'react';
import { getOrCreateGuardianPublicKey } from '../../../services/recovery/holderKeyStore';
import { keyFingerprint } from '../../../services/recovery/sealedShareRecovery';

/**
 * A would-be guardian's key, before any invitation exists
 * (/recovery/guardian-key). The guardian sends the public key to the account
 * owner directly (not through this site), and reads the fingerprint to them
 * so the owner can check the key they pasted. The private key stays in this
 * browser; the owner's device seals a share to the public key.
 */
export default function GuardianKey() {
  const [publicKey, setPublicKey] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    getOrCreateGuardianPublicKey()
      .then(setPublicKey)
      .catch(() => setError('Could not create a guardian key in this browser.'));
  }, []);

  if (error) return <p role="alert">{error}</p>;
  if (!publicKey) return <p>Creating your guardian key…</p>;

  return (
    <section data-testid="guardian-key">
      <h1>Your guardian key</h1>
      <p>
        Send this key to the person who asked you to be their guardian, by a
        message or in person. Only this browser can open the share they seal
        to it, so accept their invitation and approve recoveries from here.
      </p>
      <p role="note" data-testid="guardian-key-storage-note">
        This key is stored only in this browser, and so is your sealed share once
        you accept. Do not use a private window, and do not clear this site&apos;s
        data: if they are lost, you can no longer approve a recovery for this
        person. Tell them, so they can set up their guardians again with a new key
        from you.
      </p>
      <textarea rows="4" readOnly className="mono" value={publicKey}
        data-testid="guardian-public-key" />
      <p>
        Fingerprint, to read out so they can check the key they received:
        {' '}<strong className="mono" data-testid="guardian-key-fingerprint">
          {keyFingerprint(publicKey)}
        </strong>
      </p>
    </section>
  );
}
