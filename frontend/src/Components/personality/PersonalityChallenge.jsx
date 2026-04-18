import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import ApiService from '../../services/api';
import './PersonalityChallenge.css';

const PersonalityChallenge = () => {
  const { challengeId } = useParams();
  const navigate = useNavigate();

  const [challenge, setChallenge] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [answerText, setAnswerText] = useState('');
  const [answerChoice, setAnswerChoice] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [done, setDone] = useState(null);

  const [answeredIds, setAnsweredIds] = useState(() => new Set());
  const startedAtRef = useRef(Date.now());

  const loadChallenge = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await ApiService.personality.getChallenge(challengeId);
      setChallenge(resp.data);
      setError(null);
    } catch (err) {
      setError(ApiService.handleError(err).error || 'Failed to load challenge');
    } finally {
      setLoading(false);
    }
  }, [challengeId]);

  useEffect(() => {
    loadChallenge();
  }, [loadChallenge]);

  const activeQuestion = useMemo(() => {
    if (!challenge?.questions) return null;
    return (
      challenge.questions.find((q) => !answeredIds.has(q.id)) ||
      challenge.questions[challenge.questions.length - 1]
    );
  }, [challenge, answeredIds]);

  useEffect(() => {
    startedAtRef.current = Date.now();
    setAnswerText('');
    setAnswerChoice('');
  }, [activeQuestion?.id]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!activeQuestion || submitting) return;

    const latencyMs = Date.now() - startedAtRef.current;

    setSubmitting(true);
    setError(null);
    try {
      const resp = await ApiService.personality.submitAnswer(challengeId, {
        question_id: activeQuestion.id,
        answer_text: answerText,
        answer_choice: answerChoice,
        latency_ms: latencyMs,
      });
      const data = resp.data;
      setLastResult(data);
      setAnsweredIds((prev) => {
        const next = new Set(prev);
        next.add(activeQuestion.id);
        return next;
      });
      if (data.finished) {
        setDone(data);
      }
    } catch (err) {
      setError(ApiService.handleError(err).error || 'Failed to submit answer');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAbandon = async () => {
    if (!window.confirm('Abandon this challenge?')) return;
    try {
      await ApiService.personality.abandonChallenge(challengeId);
      navigate('/personality');
    } catch (err) {
      setError(ApiService.handleError(err).error || 'Failed to abandon challenge');
    }
  };

  if (loading) {
    return <div className="personality-challenge placeholder">Loading challenge...</div>;
  }

  if (!challenge) {
    return (
      <div className="personality-challenge error-state">
        <h2>❌ Challenge not found</h2>
        <p>{error}</p>
        <button className="btn-secondary" onClick={() => navigate('/personality')}>
          Back to Dashboard
        </button>
      </div>
    );
  }

  const total = challenge.questions?.length || 0;
  const answered = answeredIds.size;
  const progress = total > 0 ? (answered / total) * 100 : 0;

  const terminal = done || ['passed', 'failed', 'abandoned', 'expired'].includes(challenge.status);

  if (terminal) {
    const passed = done?.passed ?? challenge.status === 'passed';
    const achieved = done?.achieved_score ?? challenge.achieved_score ?? 0;
    return (
      <div className={`personality-challenge result ${passed ? 'passed' : 'failed'}`}>
        <h1>{passed ? '✅ Challenge Passed' : '❌ Challenge Failed'}</h1>
        <p className="score-line">
          Achieved score:{' '}
          <strong>{(Number(achieved) * 100).toFixed(1)}%</strong>
          {' '}of required{' '}
          <strong>{(Number(challenge.required_score) * 100).toFixed(0)}%</strong>
        </p>
        <p className="status-line">
          Status: <span className={`status-chip ${challenge.status}`}>{challenge.status}</span>
        </p>
        <button className="btn-primary" onClick={() => navigate('/personality')}>
          Back to Dashboard
        </button>
      </div>
    );
  }

  return (
    <div className="personality-challenge">
      <header>
        <h1>🧠 Personality Challenge</h1>
        <p className="meta">
          Intent: <strong>{challenge.intent}</strong> ·{' '}
          Required: <strong>{(Number(challenge.required_score) * 100).toFixed(0)}%</strong>
          {challenge.expires_at && (
            <>
              {' '}· Expires: <strong>{new Date(challenge.expires_at).toLocaleTimeString()}</strong>
            </>
          )}
        </p>
      </header>

      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>
      <p className="progress-text">
        Question {Math.min(answered + 1, total)} of {total}
      </p>

      {error && <div className="banner error">❌ {error}</div>}

      {lastResult && !lastResult.finished && (
        <div className="banner info">
          Last answer scored{' '}
          <strong>{(Number(lastResult.score) * 100).toFixed(0)}%</strong>.
          {lastResult.rationale && (
            <span className="rationale"> {lastResult.rationale}</span>
          )}
        </div>
      )}

      {activeQuestion && (
        <form className="question-card" onSubmit={handleSubmit}>
          <div className="question-head">
            <span className="pill">{activeQuestion.dimension}</span>
            <span className="pill difficulty">{activeQuestion.difficulty}</span>
          </div>

          <h2 className="prompt">{activeQuestion.prompt}</h2>

          {Array.isArray(activeQuestion.choices) && activeQuestion.choices.length > 0 ? (
            <div className="choices">
              {activeQuestion.choices.map((choice) => {
                const label = typeof choice === 'string' ? choice : choice.label || choice.value || JSON.stringify(choice);
                const value = typeof choice === 'string' ? choice : choice.value || label;
                return (
                  <label key={value} className={`choice ${answerChoice === value ? 'selected' : ''}`}>
                    <input
                      type="radio"
                      name="choice"
                      value={value}
                      checked={answerChoice === value}
                      onChange={() => setAnswerChoice(value)}
                    />
                    <span>{label}</span>
                  </label>
                );
              })}
            </div>
          ) : (
            <textarea
              rows="5"
              value={answerText}
              onChange={(e) => setAnswerText(e.target.value)}
              placeholder="Type your answer…"
              autoFocus
            />
          )}

          <div className="actions">
            <button
              type="button"
              className="btn-link danger"
              onClick={handleAbandon}
              disabled={submitting}
            >
              Abandon
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={submitting || (!answerText.trim() && !answerChoice)}
            >
              {submitting ? 'Submitting…' : 'Submit Answer'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
};

export default PersonalityChallenge;
