import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import ApiService from '../../../services/api';

/**
 * Shown on every signed-in page after a support unlock, until the owner has
 * dealt with it on the recovery activity page. A failed check shows nothing:
 * the unlock email said the same.
 */
export default function VaultExposureBanner() {
  const { pathname } = useLocation();
  const [exposed, setExposed] = useState(false);

  useEffect(() => {
    let current = true;
    ApiService.recoveryNotices.list()
      .then((resp) => { if (current) setExposed(Boolean(resp.data?.vault_exposed_since)); })
      .catch(() => {});
    return () => { current = false; };
  }, [pathname]);

  if (!exposed || pathname === '/security/recovery-notices') return null;
  return (
    <p role="alert" data-testid="vault-exposure-banner">
      Your vault may have been read during a recovery you did not start.{' '}
      <Link to="/security/recovery-notices">See what to do</Link>
    </p>
  );
}
