import React from 'react';
import { useSearchParams } from 'react-router-dom';

const ATTEMPT_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Landing page for the link in the guardian recovery email
 * (/recovery/guardian-attempt?attempt=<id>).
 *
 * POST /auth/quantum-recovery/initiate_recovery/ answers every email the same
 * way, so this link is the only place the attempt ID appears. The re-sealed
 * shares open only with the one-time key held by the client that started the
 * recovery, so this page makes no requests and holds no key, and no page in
 * this app takes the ID yet: it only says what the link is for.
 */
export default function GuardianRecoveryAttempt() {
  const [params] = useSearchParams();
  const attemptId = params.get('attempt') || '';

  if (!ATTEMPT_ID.test(attemptId)) {
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
        A guardian recovery was started for your account. It cannot be finished
        from this page: only the client that started it holds the one-time key
        that opens your guardians&apos; shares.
      </p>
      <p>Recovery ID: <code data-testid="guardian-recovery-attempt-id">{attemptId}</code></p>
      <p>
        If you did not start this recovery, use the cancel link in the same
        email.
      </p>
    </section>
  );
}
