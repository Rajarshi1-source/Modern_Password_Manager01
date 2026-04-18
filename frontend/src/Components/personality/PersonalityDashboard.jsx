import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ApiService from '../../services/api';
import './PersonalityDashboard.css';

const formatDate = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
};

const TraitBars = ({ features }) => {
  if (!features || typeof features !== 'object') return null;
  const entries = Object.entries(features).slice(0, 12);
  if (entries.length === 0) return null;
  return (
    <div className="trait-bars">
      {entries.map(([name, value]) => {
        const v = Math.max(0, Math.min(1, Number(value) || 0));
        return (
          <div className="trait-row" key={name}>
            <span className="trait-name">{name.replace(/_/g, ' ')}</span>
            <div className="trait-track">
              <div className="trait-fill" style={{ width: `${v * 100}%` }} />
            </div>
            <span className="trait-value">{(v * 100).toFixed(0)}%</span>
          </div>
        );
      })}
    </div>
  );
};

const ThemeCloud = ({ weights }) => {
  if (!weights || typeof weights !== 'object') return null;
  const entries = Object.entries(weights)
    .sort(([, a], [, b]) => Number(b) - Number(a))
    .slice(0, 16);
  if (entries.length === 0) return null;
  return (
    <div className="theme-cloud">
      {entries.map(([theme, weight]) => {
        const w = Number(weight) || 0;
        const size = 0.8 + Math.min(1.4, w);
        return (
          <span
            key={theme}
            className="theme-chip"
            style={{ fontSize: `${size}rem`, opacity: 0.5 + Math.min(0.5, w / 2) }}
          >
            {theme}
          </span>
        );
      })}
    </div>
  );
};

const PersonalityDashboard = () => {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [banner, setBanner] = useState(null);
  const navigate = useNavigate();

  const loadProfile = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await ApiService.personality.getProfile();
      setProfile(resp.data || {});
      setError(null);
    } catch (err) {
      setError(ApiService.handleError(err).error || 'Failed to load profile');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const withBusy = async (fn, successMsg) => {
    setBusy(true);
    setBanner(null);
    setError(null);
    try {
      await fn();
      if (successMsg) setBanner(successMsg);
      await loadProfile();
    } catch (err) {
      setError(ApiService.handleError(err).error || 'Operation failed');
    } finally {
      setBusy(false);
    }
  };

  const handleOptIn = () =>
    withBusy(
      () => ApiService.personality.optIn(true),
      '✅ You have opted in to personality-based authentication.'
    );

  const handleOptOut = () =>
    withBusy(
      () => ApiService.personality.optIn(false),
      'ℹ️ You have opted out. Existing profile data is preserved but not used.'
    );

  const handleInfer = () =>
    withBusy(
      () => ApiService.personality.inferProfile({ message_limit: 120 }),
      '✨ Inference triggered. Your profile will reflect updated traits shortly.'
    );

  const handleGenerate = () =>
    withBusy(
      () => ApiService.personality.generateQuestions(),
      '🧠 New personality questions have been generated.'
    );

  const handleStartChallenge = async () => {
    setBusy(true);
    setError(null);
    try {
      const resp = await ApiService.personality.startChallenge({
        intent: 'step_up',
        question_count: 3,
        required_score: 0.65,
        ttl_minutes: 10,
      });
      const challengeId = resp.data?.id;
      if (!challengeId) throw new Error('No challenge id returned');
      navigate(`/personality/challenge/${challengeId}`);
    } catch (err) {
      setError(ApiService.handleError(err).error || 'Failed to start challenge');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return <div className="personality-dashboard placeholder">Loading personality profile...</div>;
  }

  const optedIn = !!profile?.opted_in;
  const analyticsEnabled = !!profile?.analytics_enabled;
  const hasProfile = !!profile?.last_inferred_at;

  return (
    <div className="personality-dashboard">
      <header>
        <h1>🧠 Personality-Based Security</h1>
        <p className="lede">
          Use adaptive questions derived from your long-term conversational
          patterns as an additional factor for login, recovery, or step-up
          authentication.
        </p>
      </header>

      {banner && <div className="banner success">{banner}</div>}
      {error && <div className="banner error">❌ {error}</div>}

      {!analyticsEnabled && (
        <div className="banner warn">
          ⚠️ Privacy-analytics is disabled in your preferences. Enable it in
          Settings before opting in to personality auth.
        </div>
      )}

      <section className="status-grid">
        <div className={`status-card ${optedIn ? 'on' : 'off'}`}>
          <span className="status-label">Opt-In Status</span>
          <span className="status-value">{optedIn ? 'Enrolled' : 'Not Enrolled'}</span>
          <span className="status-sub">
            {optedIn && profile?.opt_in_changed_at
              ? `Since ${formatDate(profile.opt_in_changed_at)}`
              : 'You have not opted in yet'}
          </span>
        </div>
        <div className="status-card">
          <span className="status-label">Messages Analyzed</span>
          <span className="status-value">
            {profile?.source_messages_analysed ?? 0}
          </span>
          <span className="status-sub">
            {hasProfile
              ? `Last inferred ${formatDate(profile.last_inferred_at)}`
              : 'No inference yet'}
          </span>
        </div>
        <div className="status-card">
          <span className="status-label">Inference Model</span>
          <span className="status-value mono">
            {profile?.inference_model || '—'}
          </span>
          <span className="status-sub">
            {hasProfile ? 'Signed + hash-chained' : 'No profile yet'}
          </span>
        </div>
      </section>

      <section className="actions">
        {!optedIn ? (
          <button
            className="btn-primary"
            disabled={busy || !analyticsEnabled}
            onClick={handleOptIn}
          >
            {busy ? 'Working…' : 'Opt In to Personality Auth'}
          </button>
        ) : (
          <>
            <button
              className="btn-secondary"
              disabled={busy}
              onClick={handleInfer}
            >
              {busy ? 'Inferring…' : '🔍 Re-run Inference'}
            </button>
            <button
              className="btn-secondary"
              disabled={busy}
              onClick={handleGenerate}
            >
              {busy ? 'Generating…' : '🧩 Generate Question Pool'}
            </button>
            <button
              className="btn-primary"
              disabled={busy || !hasProfile}
              onClick={handleStartChallenge}
            >
              {busy ? 'Preparing…' : '🗝️ Start Test Challenge'}
            </button>
            <button
              className="btn-link danger"
              disabled={busy}
              onClick={handleOptOut}
            >
              Opt out
            </button>
          </>
        )}
      </section>

      {hasProfile && (
        <section className="profile-details">
          <div className="panel">
            <h3>Trait Features</h3>
            <TraitBars features={profile.trait_features} />
          </div>
          <div className="panel">
            <h3>Theme Weights</h3>
            <ThemeCloud weights={profile.theme_weights} />
          </div>
        </section>
      )}

      <section className="how-it-works">
        <h3>How it works</h3>
        <ol>
          <li>
            <strong>Opt in.</strong> We infer a privacy-scoped profile from
            your conversational history (stored locally where possible).
          </li>
          <li>
            <strong>Question generation.</strong> A question pool is derived
            from inferred traits, beliefs, preferences, and memories.
          </li>
          <li>
            <strong>Challenge.</strong> When you log in or request step-up, a
            short adaptive bundle is presented; you must meet the required
            consistency score to pass.
          </li>
        </ol>
      </section>
    </div>
  );
};

export default PersonalityDashboard;
