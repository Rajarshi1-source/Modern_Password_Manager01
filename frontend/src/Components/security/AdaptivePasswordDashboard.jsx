/**
 * AdaptivePasswordDashboard
 * =========================
 *
 * The adaptive-password feature's only user-facing surface (plan §5.1, gap D1).
 *
 * Until this component existed the whole feature was unreachable: three
 * components and a hook sat orphaned, referenced nowhere outside their own
 * files and their tests, `App.jsx` had no route, and the e2e spec drove
 * `[data-testid="adaptive-password-tab"]`, which nothing rendered. Every
 * guarantee the earlier phases built — the Phase 2 strength gate, the Phase 3
 * bandit, the Phase 4 memorability model — was code with no caller.
 *
 * ZERO-KNOWLEDGE BOUNDARY (the reason this file is shaped the way it is):
 *   - The raw credential is decrypted here, scored here, and rewritten to the
 *     vault here. It is never sent anywhere.
 *   - The master password is held in component state ONLY, solely to derive the
 *     fingerprint key (Argon2id, client-side). It is cleared on unmount and on
 *     lock. There is no app-wide unlocked CryptoService to borrow, and adding
 *     one would be a worse trade than asking for an explicit re-entry.
 *   - Everything that reaches the server is a keyed fingerprint, a masked
 *     preview, a substitution *class*, or a coarse aggregate score.
 */

import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import styled from 'styled-components';
import { Fingerprint, Lock, RefreshCw, Shield, ShieldAlert } from 'lucide-react';

import { CryptoService } from '../../services/cryptoService';
import { applySubstitutions } from '../../services/adaptive/adaptiveFeatures';
import { useVault } from '../../contexts/VaultContext';
import { useModalFocusTrap } from '../../hooks/useModalFocusTrap';
import AdaptivePasswordSuggestion from './AdaptivePasswordSuggestion';
import TypingProfileCard from './TypingProfileCard';
import { adaptivePasswordService } from './TypingPatternCapture';

// =============================================================================
// Styles
// =============================================================================

const Page = styled.div`
  max-width: 900px;
  margin: 0 auto;
  padding: 24px 16px 64px;
  color: #fff;
`;

const Heading = styled.header`
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;

  h1 {
    font-size: 22px;
    margin: 0;
  }
`;

const Lede = styled.p`
  margin: 0 0 24px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 14px;
  line-height: 1.5;
`;

const Panel = styled.section`
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  padding: 20px;
  margin-bottom: 20px;
`;

const PanelTitle = styled.h2`
  font-size: 15px;
  margin: 0 0 12px;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const Row = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
`;

const Field = styled.input`
  flex: 1 1 240px;
  min-width: 0;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(0, 0, 0, 0.25);
  color: #fff;
  font-size: 14px;
`;

const Select = styled.select`
  flex: 1 1 240px;
  min-width: 0;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(0, 0, 0, 0.25);
  color: #fff;
  font-size: 14px;
`;

const Action = styled.button`
  padding: 10px 16px;
  border-radius: 8px;
  border: 1px solid rgba(139, 92, 246, 0.4);
  background: ${(props) => (props.$danger ? 'rgba(239,68,68,0.15)' : 'rgba(139,92,246,0.18)')};
  border-color: ${(props) => (props.$danger ? 'rgba(239,68,68,0.4)' : 'rgba(139,92,246,0.4)')};
  color: #fff;
  font-size: 14px;
  cursor: pointer;

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const TabBar = styled.nav`
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
`;

const TabButton = styled.button`
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid
    ${(props) => (props.$active ? 'rgba(139,92,246,0.6)' : 'rgba(255,255,255,0.12)')};
  background: ${(props) => (props.$active ? 'rgba(139,92,246,0.2)' : 'transparent')};
  color: ${(props) => (props.$active ? '#fff' : 'rgba(255,255,255,0.65)')};
  font-size: 13px;
  cursor: pointer;
`;

const Note = styled.p`
  margin: 12px 0 0;
  font-size: 13px;
  color: ${(props) => (props.$error ? '#FCA5A5' : 'rgba(255,255,255,0.6)')};
  line-height: 1.5;
`;

const HistoryList = styled.ul`
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const HistoryRow = styled.li`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.2);
  font-size: 13px;
`;

const FeedbackForm = styled.li`
  padding: 12px;
  border-radius: 8px;
  background: rgba(139, 92, 246, 0.08);
  border: 1px solid rgba(139, 92, 246, 0.3);
  font-size: 13px;
  display: flex;
  flex-direction: column;
  gap: 10px;
`;

const StarRow = styled.div`
  display: flex;
  gap: 4px;
`;

const StarButton = styled.button`
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px;
  font-size: 18px;
  color: ${(props) => (props.$filled ? '#F59E0B' : 'rgba(255,255,255,0.25)')};
`;

const CheckboxLabel = styled.label`
  display: flex;
  align-items: center;
  gap: 8px;
`;

const TextArea = styled.textarea`
  width: 100%;
  min-height: 60px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(0, 0, 0, 0.25);
  color: #fff;
  font-size: 13px;
  font-family: inherit;
  resize: vertical;
`;

const ConsentBackdrop = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 1000;
`;

const ConsentCard = styled.div`
  max-width: 520px;
  width: 100%;
  background: #171727;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 14px;
  padding: 24px;
  color: #fff;
`;

const ConsentPoints = styled.ul`
  margin: 12px 0 16px;
  padding-left: 20px;
  font-size: 13px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.75);
`;

const ConsentCheck = styled.label`
  display: flex;
  gap: 10px;
  align-items: flex-start;
  font-size: 13px;
  margin-bottom: 16px;
`;

// =============================================================================
// Helpers
// =============================================================================

/**
 * Pull the password out of a decrypted vault item.
 *
 * Vault payload shapes have drifted over the project's life, so read the
 * documented key first and fall back rather than assuming one shape and
 * silently scoring `undefined`. Returns which key the value came from
 * alongside the value itself — the caller must write the adapted password
 * back to that SAME key. Always writing to `password` regardless of where
 * the value was read from would, for an item keyed under `secret`, add a
 * new `password` field while leaving the stale pre-adaptation value sitting
 * in `secret` — two different credentials on the same item, and any reader
 * that prefers `secret` would keep using the old one.
 *
 * @param {object|null} item - A decrypted vault item.
 * @returns {{ key: 'password'|'secret', value: string }|null} The field the
 *   password was read from and its value, or `null` when the item has none.
 */
function readItemPassword(item) {
    const data = item && item.data;
    if (!data || typeof data !== 'object') return null;
    if (typeof data.password === 'string' && data.password.length > 0) {
        return { key: 'password', value: data.password };
    }
    if (typeof data.secret === 'string' && data.secret.length > 0) {
        return { key: 'secret', value: data.secret };
    }
    return null;
}

/** Human label for a vault item in the picker. @private */
function itemLabel(item) {
    return item.title || item.name || item.site_name || item.url || item.item_id;
}

// =============================================================================
// Component
// =============================================================================

const AdaptivePasswordDashboard = () => {
    // `canEdit`, not `isUnlocked`: both decryptItem and updateItem go through
    // sessionVaultCrypto's session key, and `canEdit` is the reactive gate that
    // actually tracks whether that key is present. Gating on `isUnlocked`
    // instead would let the whole flow run and then throw "Unlock your vault to
    // edit items" at the vault write — after the user accepted a suggestion.
    const { items, decryptItem, updateItem, canEdit } = useVault();

    const [config, setConfig] = useState(null);
    const [configError, setConfigError] = useState(null);
    const [loading, setLoading] = useState(true);
    const [tab, setTab] = useState('profile');

    const [showConsent, setShowConsent] = useState(false);
    const [consentChecked, setConsentChecked] = useState(false);

    const [masterPassword, setMasterPassword] = useState('');
    const [fingerprinter, setFingerprinter] = useState(null);

    const [selectedItemId, setSelectedItemId] = useState('');
    const [suggestion, setSuggestion] = useState(null);
    const [busy, setBusy] = useState(false);
    const [message, setMessage] = useState(null);
    const [messageIsError, setMessageIsError] = useState(false);

    const [history, setHistory] = useState([]);
    const [pendingRollbackId, setPendingRollbackId] = useState(null);
    const [pendingDeleteConfirm, setPendingDeleteConfirm] = useState(false);

    // Feedback form (plan §4.2's input signal): at most one open at a time,
    // matching the rollback confirm's single-target pattern above.
    const [feedbackTargetId, setFeedbackTargetId] = useState(null);
    const [feedbackRating, setFeedbackRating] = useState(0);
    const [feedbackAccuracyImproved, setFeedbackAccuracyImproved] = useState(false);
    const [feedbackMemorabilityImproved, setFeedbackMemorabilityImproved] = useState(false);
    const [feedbackText, setFeedbackText] = useState('');

    // The plaintext credential is needed twice — once to score, once to write
    // the adapted value back — but must never enter React state, where it would
    // survive in the fiber tree and in devtools. A ref is dropped on unmount
    // with everything else.
    const pendingRef = useRef(null);

    // Escape and Cancel must not be able to dismiss the consent dialog while
    // `handleConfirmConsent`'s enable() request is in flight: it sets `busy`
    // before the request and only clears the dialog / shows a success toast
    // in its own then/finally, with nothing checking whether the user backed
    // out in the meantime. Dismissing mid-request only hid the dialog -- the
    // request still landed, enabling adaptive collection after the user
    // believed they had cancelled it. Same shape as the fix in
    // AdaptivePasswordSuggestion.jsx (dismiss-while-loading).
    const handleConsentClose = useCallback(() => {
        if (!busy) setShowConsent(false);
    }, [busy]);

    const consentDialogRef = useRef(null);
    useModalFocusTrap(consentDialogRef, showConsent, handleConsentClose);

    const say = useCallback((text, isError = false) => {
        setMessage(text);
        setMessageIsError(isError);
    }, []);

    const loadConfig = useCallback(async () => {
        try {
            setLoading(true);
            const data = await adaptivePasswordService.getConfig();
            setConfig(data);
            setConfigError(null);
        } catch (error) {
            // A 503 here is the deployment kill switch (ADAPTIVE_PASSWORD.ENABLED),
            // which is a different thing from "you have not opted in" and is
            // reported as such rather than as a generic failure.
            setConfigError(error);
            setConfig(null);
        } finally {
            setLoading(false);
        }
    }, []);

    const loadHistory = useCallback(async () => {
        try {
            const data = await adaptivePasswordService.getHistory();
            setHistory(data.adaptations || []);
        } catch (error) {
            console.error('Failed to load adaptation history:', error);
        }
    }, []);

    useEffect(() => {
        loadConfig();
    }, [loadConfig]);

    useEffect(() => {
        if (config?.enabled) loadHistory();
    }, [config?.enabled, loadHistory]);

    // Drop every secret this component held the moment it goes away.
    useEffect(() => () => {
        pendingRef.current = null;
    }, []);

    const enabled = Boolean(config?.enabled);
    const featureDisabled = configError?.response?.status === 503;

    const credentials = useMemo(
        () => (items || []).filter((item) => item && item.item_id),
        [items],
    );

    // -------------------------------------------------------------------------
    // Consent
    // -------------------------------------------------------------------------

    const handleToggleClick = useCallback(() => {
        if (enabled) {
            setBusy(true);
            // Clear the master password immediately, not just the derived
            // fingerprinter: a user can type it into the unlock form and then
            // change their mind and disable before ever submitting, which
            // would otherwise leave it sitting in component state
            // indefinitely — outliving the derivation it existed for.
            setMasterPassword('');
            adaptivePasswordService
                .disable()
                .then(() => {
                    setFingerprinter(null);
                    setSuggestion(null);
                    return loadConfig();
                })
                .catch((error) => say(error.message || 'Could not disable.', true))
                .finally(() => setBusy(false));
            return;
        }
        setConsentChecked(false);
        setShowConsent(true);
    }, [enabled, loadConfig, say]);

    const handleConfirmConsent = useCallback(async () => {
        setBusy(true);
        try {
            await adaptivePasswordService.enable();
            setShowConsent(false);
            await loadConfig();
            say('Adaptive passwords enabled.');
        } catch (error) {
            say(error.message || 'Could not enable adaptive passwords.', true);
        } finally {
            setBusy(false);
        }
    }, [loadConfig, say]);

    // -------------------------------------------------------------------------
    // Fingerprint key
    // -------------------------------------------------------------------------

    const handleUnlockAdaptive = useCallback(
        async (event) => {
            event.preventDefault();
            if (!masterPassword) return;
            setBusy(true);
            try {
                const crypto = new CryptoService(masterPassword);
                const fingerprint = adaptivePasswordService.makeFingerprinter(
                    crypto,
                    config.fingerprint_salt,
                );
                // Derive once here rather than lazily at apply time, so
                // deriving is a one-time cost rather than paid on every
                // fingerprint call. This does NOT verify the password itself:
                // Argon2id has no "wrong password" outcome, it deterministically
                // derives DIFFERENT (but equally well-formed) key material from
                // any input, so a mistyped password "succeeds" here and silently
                // fingerprints under the wrong key for the rest of the session.
                // The vault write later still uses the vault's own, correctly
                // authenticated session key, so the credential itself is never
                // at risk — only this feature's own fingerprint-keyed
                // bookkeeping (rollback chain, history) gets orphaned. Verifying
                // the typed password against the vault's already-unlocked key
                // material would close this, but needs plumbing this component
                // doesn't have (a stored auth-hash/salt, or a decrypt-and-compare
                // against a known item) — flagged as a follow-up rather than
                // built here under time pressure.
                // Investigated (round 3 review) whether `sessionVaultCrypto.
                // unlockWithVaultPassword` could be reused directly: it DOES
                // genuinely verify a password (AES-GCM unwrap of a stored
                // wrapped DEK fails loudly on the wrong key), but it's scoped
                // to the OAuth/social-login path specifically ("the user has
                // no master password" per its own caller's docstring,
                // VaultUnlockModal.jsx) — calling it here would conflate two
                // potentially-different secrets and mutate that module's own
                // session-key state as a side effect. Standard (non-OAuth)
                // login never calls it either (grepped VaultContext.jsx and
                // useAuth.jsx: zero hits), so no drop-in "verify the master
                // password" primitive exists for the common case today. A
                // real fix needs tracing the actual login-time key-derivation
                // flow end to end, not a same-round graft of an
                // OAuth-specific helper onto a different authentication
                // concept.
                await fingerprint('adaptive-probe');
                // `fingerprint` is a closure over `crypto`, and CryptoService
                // keeps the raw password on `this.masterPassword` for the
                // instance's whole lifetime -- so clearing the React state
                // below is not enough on its own; the password would still be
                // reachable through this closure for the rest of the adaptive
                // session. Scrub it directly rather than calling the
                // existing `crypto.clearKeys()`: that also drops
                // `_fpKeyCache`, which is exactly what lets every LATER
                // `fingerprint(password)` call skip re-deriving from
                // `masterPassword` in the first place (see
                // deriveFingerprintKey's cache-hit branch) -- clearing it
                // here would silently break every fingerprint after this one.
                crypto.masterPassword = null;
                setFingerprinter(() => fingerprint);
                say('Adaptive learning unlocked for this session.');
            } catch (error) {
                say(
                    error.message
                        || 'Could not derive the fingerprint key from that password.',
                    true,
                );
            } finally {
                // Clear the master password from state as soon as the key
                // exists; the derived HMAC key is non-extractable and is all
                // the rest of this session needs.
                setMasterPassword('');
                setBusy(false);
            }
        },
        [masterPassword, config, say],
    );

    // -------------------------------------------------------------------------
    // Suggestion + vault rotation (plan §5.3, gap C2)
    // -------------------------------------------------------------------------

    const handleSuggest = useCallback(async () => {
        if (!selectedItemId) return;
        setBusy(true);
        setSuggestion(null);
        say(null);
        try {
            const decrypted = await decryptItem(selectedItemId);
            if (!decrypted || decrypted._decryptionFailed) {
                say('That item could not be decrypted, so it was not analysed.', true);
                return;
            }
            const read = readItemPassword(decrypted);
            if (!read) {
                say('That item has no password field to adapt.', true);
                return;
            }
            const { key: passwordKey, value: password } = read;

            const result = await adaptivePasswordService.suggestAdaptation(password);
            if (!result.has_suggestion) {
                // Not an error. The Phase 2 gate rejects roughly three quarters
                // of candidate substitutions by design, so "no change needed"
                // is the ordinary outcome and is worded as one.
                say(result.reason || 'No change needed for this password.');
                return;
            }

            pendingRef.current = {
                itemId: selectedItemId, password, passwordKey, decrypted,
            };
            setSuggestion(result);
        } catch (error) {
            say(error.message || 'Could not analyse that credential.', true);
        } finally {
            setBusy(false);
        }
    }, [selectedItemId, decryptItem, say]);

    const applyToVault = useCallback(
        async (accepted) => {
            const pending = pendingRef.current;
            if (!pending || !accepted?.substitutions?.length) return;
            if (typeof fingerprinter !== 'function') {
                say('Unlock adaptive learning before applying a change.', true);
                return;
            }

            setBusy(true);
            try {
                const adaptedPassword = applySubstitutions(
                    pending.password,
                    accepted.substitutions,
                );

                // ORDERING IS LOAD-BEARING (plan §5.3): the vault write goes
                // first. If the analytics POST below then fails, the user has a
                // working credential and a missing record. The reverse ordering
                // loses the password: the server would hold a record of a
                // rotation the vault never performed, and the adapted value only
                // ever existed in this tab's memory.
                await updateItem({
                    ...pending.decrypted,
                    data: {
                        ...pending.decrypted.data,
                        [pending.passwordKey]: adaptedPassword,
                    },
                });

                try {
                    await adaptivePasswordService.applyAdaptation(
                        pending.password,
                        accepted.substitutions,
                        {
                            fingerprint: fingerprinter,
                            fpKeyVersion: config.fp_key_version,
                            memorabilityImprovement: accepted.memorability_improvement,
                            memorabilityScoreBefore: accepted.memorability_score_before,
                            memorabilityScoreAfter: accepted.memorability_score_after,
                            memorabilityDriver: accepted.memorability_driver,
                        },
                    );
                    say('Password updated in your vault.');
                } catch (recordError) {
                    console.error('Adaptation record failed after vault write:', recordError);
                    say(
                        'Password updated in your vault, but the learning record '
                        + 'could not be saved. Nothing was lost.',
                    );
                }

                await loadHistory();
                await loadConfig();
            } catch (error) {
                say(
                    error.message
                        || 'Could not update the credential; nothing was changed.',
                    true,
                );
            } finally {
                pendingRef.current = null;
                setSuggestion(null);
                setBusy(false);
            }
        },
        [fingerprinter, config, updateItem, loadHistory, loadConfig, say],
    );

    const handleReject = useCallback(() => {
        pendingRef.current = null;
        setSuggestion(null);
        say('Suggestion dismissed.');
    }, [say]);

    const handleRollback = useCallback(
        async (adaptationId) => {
            setBusy(true);
            try {
                await adaptivePasswordService.rollback(adaptationId);
                say(
                    'Rolled back. Your vault entry was NOT changed back '
                    + 'automatically — restore it from item history if needed.',
                );
                await loadHistory();
            } catch (error) {
                say(error.message || 'Could not roll back.', true);
            } finally {
                setPendingRollbackId(null);
                setBusy(false);
            }
        },
        [loadHistory, say],
    );

    const handleOpenFeedback = useCallback((adaptationId) => {
        setFeedbackTargetId(adaptationId);
        setFeedbackRating(0);
        setFeedbackAccuracyImproved(false);
        setFeedbackMemorabilityImproved(false);
        setFeedbackText('');
    }, []);

    const handleSubmitFeedback = useCallback(async () => {
        if (!feedbackTargetId || feedbackRating < 1) return;
        setBusy(true);
        try {
            await adaptivePasswordService.submitFeedback(feedbackTargetId, {
                rating: feedbackRating,
                typingAccuracyImproved: feedbackAccuracyImproved,
                memorabilityImproved: feedbackMemorabilityImproved,
                additionalFeedback: feedbackText,
            });
            say('Feedback submitted.');
            setFeedbackTargetId(null);
        } catch (error) {
            say(error.message || 'Could not submit feedback.', true);
        } finally {
            setBusy(false);
        }
    }, [
        feedbackTargetId, feedbackRating, feedbackAccuracyImproved,
        feedbackMemorabilityImproved, feedbackText, say,
    ]);

    const handleExport = useCallback(async () => {
        try {
            const data = await adaptivePasswordService.exportData();
            const blob = new Blob([JSON.stringify(data, null, 2)], {
                type: 'application/json',
            });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = 'adaptive-password-data.json';
            link.click();
            // Deferred, not synchronous: some browsers cancel a download
            // that's still starting if its blob URL is revoked in the same
            // tick as the click that triggered it.
            setTimeout(() => URL.revokeObjectURL(url), 0);
            say('Export complete.');
        } catch (error) {
            say(error.message || 'Export failed.', true);
        }
    }, [say]);

    // GDPR erasure (plan §7, service `delete_all_data`): deliberately reachable
    // whether or not the feature is currently enabled — `/adaptive/data/` is
    // not behind `@require_adaptive_enabled` server-side either, because
    // opting out and erasing data are rights, not features. Two-step confirm,
    // matching the rollback flow's own click-then-confirm pattern above.
    const handleDeleteAllData = useCallback(async () => {
        setBusy(true);
        try {
            await adaptivePasswordService.deleteAllData();
            say('Data deleted.');
            setFingerprinter(null);
            setSuggestion(null);
            setHistory([]);
            await loadConfig();
        } catch (error) {
            say(error.message || 'Could not delete your data.', true);
        } finally {
            setPendingDeleteConfirm(false);
            setBusy(false);
        }
    }, [loadConfig, say]);

    // -------------------------------------------------------------------------
    // Render
    // -------------------------------------------------------------------------

    if (loading) {
        return (
            <Page data-testid="adaptive-password-section">
                <Heading>
                    <Fingerprint size={22} />
                    <h1>Adaptive Password</h1>
                </Heading>
                <Note>Loading your adaptive settings…</Note>
            </Page>
        );
    }

    // featureDisabled is NOT an early return (it was — see round-1 fix history):
    // GDPR export (`/adaptive/export/`) and erasure (`/adaptive/data/`) are
    // deliberately not gated by the deployment kill switch server-side (same
    // reasoning as the opted-out case just above), so a full-page replacement
    // here made both permanently unreachable the moment ADAPTIVE_PASSWORD.ENABLED
    // was off — the config fetch that produces this state is itself gated,
    // but the erasure/export endpoints it blocks the REST of the page for are
    // not. `config` stays `null` in this state, so `enabled` is already
    // `false` and the existing `!enabled` data-panel fallback below applies
    // without further changes.

    return (
        <Page data-testid="adaptive-password-section">
            <Heading>
                <Fingerprint size={22} />
                <h1>Adaptive Password</h1>
            </Heading>
            <Lede>
                Your password gradually morphs toward substitutions you already
                type fluently. Every suggestion is generated on this device and
                must first pass a strength check — a change that would make a
                password easier to guess is never offered.
            </Lede>

            <Panel>
                <Row>
                    <PanelTitle style={{ margin: 0, flex: '1 1 auto' }}>
                        {featureDisabled ? <ShieldAlert size={16} /> : <Shield size={16} />}
                        {featureDisabled ? 'Unavailable' : (enabled ? 'Enabled' : 'Disabled')}
                    </PanelTitle>
                    {/* No config exists to toggle while the deployment kill
                        switch is on -- calling enable() would just 503 too. */}
                    {!featureDisabled && (
                        <Action
                            type="button"
                            onClick={handleToggleClick}
                            disabled={busy}
                            data-testid="adaptive-enable-toggle"
                            $danger={enabled}
                        >
                            {enabled ? 'Turn off' : 'Turn on'}
                        </Action>
                    )}
                </Row>
                {featureDisabled && (
                    <Note $error>
                        Adaptive passwords are switched off for this deployment.
                        You can still export or erase any data already collected.
                    </Note>
                )}
                {!enabled && !featureDisabled && (
                    <Note data-testid="adaptive-status-disabled">
                        Adaptive passwords are off. Nothing about your typing is
                        collected until you opt in.
                    </Note>
                )}
                {enabled && config?.should_suggest && (
                    <Note>
                        A new suggestion is due — your cadence is every{' '}
                        {config.suggestion_frequency_days} days.
                    </Note>
                )}
                {enabled && config && !config.should_suggest && (
                    <Note>
                        Not due for a suggestion yet (every{' '}
                        {config.suggestion_frequency_days} days). You can still
                        check a credential manually below.
                    </Note>
                )}
                {message && <Note $error={messageIsError}>{message}</Note>}
            </Panel>

            {/* The tab bar and "Your data" are NOT gated on `enabled` as a
                block, unlike the other three tabs: `/adaptive/export/` and
                `/adaptive/data/` (erasure) are deliberately reachable
                whether or not the feature is currently on (same GDPR
                reasoning as the backend's own `disable_adaptive_passwords`
                view docstring), so the UI path to them must survive opting
                out too. `tab === 'data' || !enabled` falls back to the data
                panel automatically when the feature is off, regardless of
                which tab was last selected before it was turned off. */}
            <TabBar>
                {enabled && (
                    <>
                        <TabButton
                            type="button"
                            $active={tab === 'profile'}
                            onClick={() => setTab('profile')}
                            data-testid="profile-tab"
                        >
                            Typing profile
                        </TabButton>
                        <TabButton
                            type="button"
                            $active={tab === 'adapt'}
                            onClick={() => setTab('adapt')}
                            data-testid="adapt-tab"
                        >
                            Adapt a credential
                        </TabButton>
                        <TabButton
                            type="button"
                            $active={tab === 'history'}
                            onClick={() => setTab('history')}
                            data-testid="history-tab"
                        >
                            History
                        </TabButton>
                    </>
                )}
                <TabButton
                    type="button"
                    $active={tab === 'data' || !enabled}
                    onClick={() => setTab('data')}
                    data-testid="data-management-tab"
                >
                    Your data
                </TabButton>
            </TabBar>

            {enabled && tab === 'profile' && <TypingProfileCard showToggle={false} />}

            {enabled && tab === 'adapt' && (
                        <Panel>
                            <PanelTitle>
                                <Lock size={16} />
                                Adapt a stored credential
                            </PanelTitle>

                            {!canEdit && (
                                <Note $error>
                                    Unlock your vault first — the credential has to
                                    be decrypted on this device to be analysed.
                                </Note>
                            )}

                            {canEdit && typeof fingerprinter !== 'function' ? (
                                <form onSubmit={handleUnlockAdaptive}>
                                    <Note>
                                        Re-enter your master password to derive this
                                        session&apos;s fingerprint key. It is used
                                        locally by Argon2id and is never sent
                                        anywhere.
                                    </Note>
                                    <Row style={{ marginTop: 12 }}>
                                        <Field
                                            type="password"
                                            autoComplete="current-password"
                                            placeholder="Master password"
                                            value={masterPassword}
                                            onChange={(e) => setMasterPassword(e.target.value)}
                                            data-testid="adaptive-master-password"
                                        />
                                        <Action type="submit" disabled={busy || !masterPassword}>
                                            {busy ? 'Deriving…' : 'Unlock'}
                                        </Action>
                                    </Row>
                                </form>
                            ) : null}

                            {canEdit && typeof fingerprinter === 'function' && (
                                <Row>
                                    <Select
                                        value={selectedItemId}
                                        onChange={(e) => setSelectedItemId(e.target.value)}
                                        data-testid="adaptive-credential-select"
                                        aria-label="Credential to adapt"
                                    >
                                        <option value="">Choose a credential…</option>
                                        {credentials.map((item) => (
                                            <option key={item.item_id} value={item.item_id}>
                                                {itemLabel(item)}
                                            </option>
                                        ))}
                                    </Select>
                                    <Action
                                        type="button"
                                        onClick={handleSuggest}
                                        disabled={busy || !selectedItemId}
                                        data-testid="suggest-adaptation-button"
                                    >
                                        <RefreshCw size={14} />{' '}
                                        {busy ? 'Checking…' : 'Check for a better version'}
                                    </Action>
                                </Row>
                            )}
                        </Panel>
                    )}

                    {enabled && tab === 'history' && (
                        <Panel>
                            <PanelTitle>Adaptation history</PanelTitle>
                            {history.length === 0 ? (
                                <Note>No adaptations recorded in this key era yet.</Note>
                            ) : (
                                <HistoryList data-testid="adaptation-history-list">
                                    {history.map((entry) => (
                                        <Fragment key={entry.id}>
                                            <HistoryRow>
                                                <span>
                                                    Generation {entry.generation} · {entry.status}
                                                    {entry.suggested_at
                                                        && ` · ${new Date(entry.suggested_at).toLocaleDateString()}`}
                                                </span>
                                                <Row style={{ gap: 8 }}>
                                                    <Action
                                                        type="button"
                                                        disabled={busy}
                                                        onClick={() => handleOpenFeedback(entry.id)}
                                                        data-testid="feedback-button"
                                                    >
                                                        Give feedback
                                                    </Action>
                                                    {entry.can_rollback
                                                        && (pendingRollbackId === entry.id ? (
                                                            <Action
                                                                type="button"
                                                                disabled={busy}
                                                                onClick={() => handleRollback(entry.id)}
                                                                data-testid="confirm-rollback-button"
                                                            >
                                                                Confirm rollback
                                                            </Action>
                                                        ) : (
                                                            <Action
                                                                type="button"
                                                                disabled={busy}
                                                                onClick={() => setPendingRollbackId(entry.id)}
                                                                data-testid="rollback-button"
                                                            >
                                                                Roll back
                                                            </Action>
                                                        ))}
                                                </Row>
                                            </HistoryRow>

                                            {feedbackTargetId === entry.id && (
                                                <FeedbackForm>
                                                    <StarRow role="radiogroup" aria-label="Rating">
                                                        {[1, 2, 3, 4, 5].map((star) => (
                                                            <StarButton
                                                                key={star}
                                                                type="button"
                                                                $filled={star <= feedbackRating}
                                                                onClick={() => setFeedbackRating(star)}
                                                                aria-label={`${star} star${star === 1 ? '' : 's'}`}
                                                                data-testid={`rating-star-${star}`}
                                                            >
                                                                ★
                                                            </StarButton>
                                                        ))}
                                                    </StarRow>
                                                    <CheckboxLabel>
                                                        <input
                                                            type="checkbox"
                                                            checked={feedbackAccuracyImproved}
                                                            onChange={(e) =>
                                                                setFeedbackAccuracyImproved(e.target.checked)}
                                                            data-testid="accuracy-improved-checkbox"
                                                        />
                                                        Typing accuracy improved
                                                    </CheckboxLabel>
                                                    <CheckboxLabel>
                                                        <input
                                                            type="checkbox"
                                                            checked={feedbackMemorabilityImproved}
                                                            onChange={(e) =>
                                                                setFeedbackMemorabilityImproved(e.target.checked)}
                                                            data-testid="memorability-improved-checkbox"
                                                        />
                                                        Easier to remember
                                                    </CheckboxLabel>
                                                    <TextArea
                                                        placeholder="Anything else? (optional)"
                                                        value={feedbackText}
                                                        onChange={(e) => setFeedbackText(e.target.value)}
                                                        data-testid="feedback-text"
                                                    />
                                                    <Row>
                                                        <Action
                                                            type="button"
                                                            disabled={busy || feedbackRating < 1}
                                                            onClick={handleSubmitFeedback}
                                                            data-testid="submit-feedback-button"
                                                        >
                                                            Submit feedback
                                                        </Action>
                                                        <Action
                                                            type="button"
                                                            onClick={() => setFeedbackTargetId(null)}
                                                        >
                                                            Cancel
                                                        </Action>
                                                    </Row>
                                                </FeedbackForm>
                                            )}
                                        </Fragment>
                                    ))}
                                </HistoryList>
                            )}
                        </Panel>
                    )}

            {(tab === 'data' || !enabled) && (
                <Panel>
                    <PanelTitle>Your data</PanelTitle>
                    <Note>
                        Export or erase everything this feature has learned.
                        Both work even if the feature is switched off for
                        the deployment — they are GDPR rights, not
                        features.
                    </Note>
                    <Row style={{ marginTop: 12 }}>
                        <Action
                            type="button"
                            onClick={handleExport}
                            data-testid="export-data-button"
                        >
                            Export my data
                        </Action>
                        {pendingDeleteConfirm ? (
                            <Action
                                type="button"
                                $danger
                                disabled={busy}
                                onClick={handleDeleteAllData}
                                data-testid="confirm-delete-button"
                            >
                                Confirm delete
                            </Action>
                        ) : (
                            <Action
                                type="button"
                                $danger
                                disabled={busy}
                                onClick={() => setPendingDeleteConfirm(true)}
                                data-testid="delete-data-button"
                            >
                                Delete all my data
                            </Action>
                        )}
                    </Row>
                </Panel>
            )}

            {showConsent && (
                <ConsentBackdrop role="presentation">
                    <ConsentCard
                        ref={consentDialogRef}
                        tabIndex={-1}
                        data-testid="consent-dialog"
                        role="dialog"
                        aria-modal="true"
                        aria-label="Adaptive password consent"
                    >
                        <h2 style={{ marginTop: 0, fontSize: 17 }}>
                            Before you turn this on
                        </h2>
                        <ConsentPoints>
                            <li>
                                We record coarse <strong>typing patterns</strong> —
                                bucketed key timings and the positions where you
                                correct yourself. Never keystrokes, never the
                                password.
                            </li>
                            <li>
                                Aggregates are protected with{' '}
                                <strong>differential privacy</strong> before they
                                are combined with anyone else&apos;s.
                            </li>
                            <li>
                                Suggestions are generated on this device and must
                                pass a strength check first.
                            </li>
                            <li>You can export or erase everything at any time.</li>
                        </ConsentPoints>
                        <ConsentCheck>
                            <input
                                type="checkbox"
                                checked={consentChecked}
                                onChange={(e) => setConsentChecked(e.target.checked)}
                                data-testid="consent-checkbox"
                            />
                            <span>
                                I understand and consent to adaptive password
                                learning.
                            </span>
                        </ConsentCheck>
                        <Row>
                            <Action
                                type="button"
                                onClick={handleConsentClose}
                                disabled={busy}
                                data-testid="cancel-consent-button"
                            >
                                Cancel
                            </Action>
                            <Action
                                type="button"
                                onClick={handleConfirmConsent}
                                disabled={!consentChecked || busy}
                                data-testid="confirm-consent-button"
                            >
                                Enable
                            </Action>
                        </Row>
                    </ConsentCard>
                </ConsentBackdrop>
            )}

            {suggestion && (
                <AdaptivePasswordSuggestion
                    suggestion={suggestion}
                    isLoading={busy}
                    onAccept={applyToVault}
                    onReject={handleReject}
                    onClose={handleReject}
                />
            )}
        </Page>
    );
};

export default AdaptivePasswordDashboard;
