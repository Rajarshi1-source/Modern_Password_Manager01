import React from 'react';
import { useSearchParams } from 'react-router-dom';

/**
 * Landing page for the link in the guardian recovery email
 * (/recovery/guardian-attempt?attempt=<id>).
 *
 * POST /auth/quantum-recovery/initiate_recovery/ answers every email the same
 * way, so this link is the only place the attempt ID appears. The re-sealed
 * shares open only with the one-time key on the device that started the
 * recovery, so this page makes no requests and holds no key: it gives the
 * person the ID to use on that device.
 */
export default function GuardianRecoveryAttempt() {
  const [params] = useSearchParams();
  const attemptId = params.get('attempt') || '';

  if (!attemptId) {
    return (
      <section data-testid="guardian-recovery-attempt">
        <h1>Guardian recovery</h1>
        <p role="alert">This link is incomplete. Open the link from the email again.</p>
      </section>
    );
  }

  return (
    <section data-testid="guardian-recovery-attempt">
      <h1>Guardian recovery</h1>
      <p>
        Finish this recovery on the device that started it. That device holds
        the one-time key that opens your guardians&apos; shares, and it needs
        this recovery ID:
      </p>
      <p><code data-testid="guardian-recovery-attempt-id">{attemptId}</code></p>
      <p>
        If you did not start this recovery, use the cancel link in the same
        email.
      </p>
    </section>
  );
}
