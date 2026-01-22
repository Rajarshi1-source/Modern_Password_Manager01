/**
 * Time-Lock Countdown Component
 * =============================
 * 
 * Animated countdown timer for time-lock capsules.
 * Shows remaining time until password becomes accessible.
 * 
 * Enhanced with:
 * - VDF computation progress indicator
 * - Beneficiary status display
 * - Will/Escrow status badges
 */

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const TimeLockCountdown = ({
  unlockAt,
  onUnlocked,
  capsuleId,
  beneficiaryEmail,
  showDetails = true,
  // New enhanced props
  capsuleType = 'general',  // general, will, escrow, time_capsule, emergency
  mode = 'server',          // server, client, hybrid
  vdfProgress = null,       // { percent, iterationsDone, estimatedRemaining }
  beneficiaries = [],       // List of beneficiaries
  willStatus = null,        // { daysUntilTrigger, lastCheckIn }
  escrowStatus = null,      // { approvalCount, totalParties, condition }
}) => {
  const [timeRemaining, setTimeRemaining] = useState(null);
  const [isUnlocked, setIsUnlocked] = useState(false);
  const [showBeneficiaries, setShowBeneficiaries] = useState(false);

  // Calculate time remaining
  const calculateTimeRemaining = useCallback(() => {
    const now = new Date();
    const unlock = new Date(unlockAt);
    const diff = unlock - now;

    if (diff <= 0) {
      setIsUnlocked(true);
      if (onUnlocked) onUnlocked();
      return null;
    }

    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((diff % (1000 * 60)) / 1000);

    return { days, hours, minutes, seconds, totalSeconds: Math.floor(diff / 1000) };
  }, [unlockAt, onUnlocked]);

  // Update countdown every second
  useEffect(() => {
    setTimeRemaining(calculateTimeRemaining());

    const interval = setInterval(() => {
      setTimeRemaining(calculateTimeRemaining());
    }, 1000);

    return () => clearInterval(interval);
  }, [calculateTimeRemaining]);

  // Calculate progress percentage
  const getProgress = () => {
    if (!timeRemaining || isUnlocked) return 100;
    return Math.max(0, 100 - (timeRemaining.totalSeconds / 259200) * 100); // 72 hours
  };

  // Get capsule type badge
  const getTypeBadge = () => {
    const badges = {
      general: { icon: '🔐', label: 'Time-Lock', color: '#6366f1' },
      will: { icon: '📜', label: 'Password Will', color: '#fbbf24' },
      escrow: { icon: '🤝', label: 'Escrow', color: '#10b981' },
      time_capsule: { icon: '⏳', label: 'Time Capsule', color: '#f59e0b' },
      emergency: { icon: '🚨', label: 'Emergency', color: '#ef4444' }
    };
    return badges[capsuleType] || badges.general;
  };

  const typeBadge = getTypeBadge();

  if (isUnlocked) {
    return (
      <motion.div
        className="timelock-countdown unlocked"
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
      >
        <div className="unlock-icon">🔓</div>
        <h3>Capsule Unlocked!</h3>
        <p>Your password is now accessible</p>

        {beneficiaries.length > 0 && (
          <div className="beneficiary-notified">
            📧 {beneficiaries.length} beneficiaries notified
          </div>
        )}

        <style jsx>{`
          .timelock-countdown.unlocked {
            background: linear-gradient(135deg, #22c55e20 0%, #16a34a20 100%);
            border: 1px solid #22c55e40;
            border-radius: 16px;
            padding: 24px;
            text-align: center;
          }
          .unlock-icon {
            font-size: 48px;
            margin-bottom: 12px;
          }
          h3 {
            color: #22c55e;
            margin: 0 0 8px;
          }
          p {
            color: #9ca3af;
            margin: 0;
          }
          .beneficiary-notified {
            margin-top: 16px;
            padding: 8px 16px;
            background: rgba(34, 197, 94, 0.2);
            border-radius: 8px;
            color: #22c55e;
            font-size: 14px;
          }
        `}</style>
      </motion.div>
    );
  }

  if (!timeRemaining) {
    return (
      <div className="timelock-countdown loading">
        <div className="spinner" />
        <p>Loading...</p>
      </div>
    );
  }

  return (
    <div className="timelock-countdown">
      {/* Type Badge */}
      <div className="type-badge" style={{ borderColor: typeBadge.color }}>
        <span className="badge-icon">{typeBadge.icon}</span>
        <span className="badge-label" style={{ color: typeBadge.color }}>
          {typeBadge.label}
        </span>
      </div>

      {/* Lock Icon */}
      <div className="lock-icon-container">
        <motion.div
          className="lock-icon"
          animate={{
            rotateZ: [0, -5, 5, -5, 0],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            repeatDelay: 5
          }}
        >
          🔒
        </motion.div>
      </div>

      {/* Time Units */}
      <div className="time-units">
        <TimeUnit value={timeRemaining.days} label="Days" />
        <Separator />
        <TimeUnit value={timeRemaining.hours} label="Hours" />
        <Separator />
        <TimeUnit value={timeRemaining.minutes} label="Minutes" />
        <Separator />
        <TimeUnit value={timeRemaining.seconds} label="Seconds" />
      </div>

      {/* Progress Bar */}
      <div className="progress-container">
        <div className="progress-track">
          <motion.div
            className="progress-fill"
            initial={{ width: '0%' }}
            animate={{ width: `${getProgress()}%` }}
            transition={{ duration: 0.5 }}
          />
        </div>
        <span className="progress-label">Time elapsed</span>
      </div>

      {/* VDF Progress (for client/hybrid mode) */}
      {(mode === 'client' || mode === 'hybrid') && vdfProgress && (
        <div className="vdf-progress">
          <div className="vdf-header">
            <span className="vdf-icon">⚡</span>
            <span className="vdf-title">VDF Computation</span>
            <span className="vdf-percent">{vdfProgress.percent?.toFixed(1)}%</span>
          </div>
          <div className="vdf-bar">
            <div
              className="vdf-fill"
              style={{ width: `${vdfProgress.percent || 0}%` }}
            />
          </div>
          {vdfProgress.estimatedRemaining && (
            <span className="vdf-eta">
              ~{vdfProgress.estimatedRemaining}s remaining
            </span>
          )}
        </div>
      )}

      {/* Password Will Status */}
      {capsuleType === 'will' && willStatus && (
        <div className="will-status">
          <div className="status-header">
            <span className="status-icon">📜</span>
            <span className="status-title">Dead Man's Switch</span>
          </div>
          <div className="status-content">
            <div className="status-item">
              <span>Days until trigger:</span>
              <strong>{willStatus.daysUntilTrigger}</strong>
            </div>
            <div className="status-item">
              <span>Last check-in:</span>
              <strong>{new Date(willStatus.lastCheckIn).toLocaleDateString()}</strong>
            </div>
          </div>
        </div>
      )}

      {/* Escrow Status */}
      {capsuleType === 'escrow' && escrowStatus && (
        <div className="escrow-status">
          <div className="status-header">
            <span className="status-icon">🤝</span>
            <span className="status-title">Escrow Status</span>
          </div>
          <div className="approval-meter">
            <div className="approval-bar">
              <div
                className="approval-fill"
                style={{
                  width: `${(escrowStatus.approvalCount / escrowStatus.totalParties) * 100}%`
                }}
              />
            </div>
            <span className="approval-text">
              {escrowStatus.approvalCount} / {escrowStatus.totalParties} approved
            </span>
          </div>
          <div className="condition-badge">
            Condition: {escrowStatus.condition}
          </div>
        </div>
      )}

      {/* Beneficiaries Section */}
      {beneficiaries.length > 0 && (
        <div className="beneficiaries-section">
          <button
            className="beneficiaries-toggle"
            onClick={() => setShowBeneficiaries(!showBeneficiaries)}
          >
            <span>👥 {beneficiaries.length} Beneficiaries</span>
            <span className="toggle-icon">{showBeneficiaries ? '▲' : '▼'}</span>
          </button>

          <AnimatePresence>
            {showBeneficiaries && (
              <motion.div
                className="beneficiaries-list"
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
              >
                {beneficiaries.map((ben, idx) => (
                  <div key={idx} className="beneficiary-item">
                    <div className="ben-avatar">
                      {ben.name?.charAt(0) || '?'}
                    </div>
                    <div className="ben-info">
                      <span className="ben-name">{ben.name}</span>
                      <span className="ben-email">{ben.email}</span>
                    </div>
                    <span className={`ben-status ${ben.verified ? 'verified' : 'pending'}`}>
                      {ben.verified ? '✓' : '○'}
                    </span>
                  </div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* Details */}
      {showDetails && (
        <div className="capsule-details">
          {capsuleId && (
            <div className="detail-item">
              <span className="detail-label">Capsule ID:</span>
              <span className="detail-value">{capsuleId.slice(0, 8)}...</span>
            </div>
          )}
          {beneficiaryEmail && (
            <div className="detail-item">
              <span className="detail-label">Notify:</span>
              <span className="detail-value">{beneficiaryEmail}</span>
            </div>
          )}
          <div className="detail-item">
            <span className="detail-label">Unlocks at:</span>
            <span className="detail-value">
              {new Date(unlockAt).toLocaleString()}
            </span>
          </div>
          <div className="detail-item">
            <span className="detail-label">Mode:</span>
            <span className="detail-value mode-badge">
              {mode === 'server' && '🖥️ Server'}
              {mode === 'client' && '💻 Client VDF'}
              {mode === 'hybrid' && '🔄 Hybrid'}
            </span>
          </div>
        </div>
      )}

      <style jsx>{`
        .timelock-countdown {
          background: linear-gradient(135deg, #1e1e3f 0%, #0f0f23 100%);
          border: 1px solid rgba(99, 102, 241, 0.3);
          border-radius: 16px;
          padding: 24px;
        }

        .type-badge {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 6px 12px;
          border: 1px solid;
          border-radius: 20px;
          margin-bottom: 16px;
          background: rgba(0, 0, 0, 0.2);
        }

        .badge-icon {
          font-size: 16px;
        }

        .badge-label {
          font-size: 12px;
          font-weight: 600;
          text-transform: uppercase;
        }

        .lock-icon-container {
          text-align: center;
          margin-bottom: 20px;
        }

        .lock-icon {
          font-size: 48px;
          display: inline-block;
        }

        .time-units {
          display: flex;
          justify-content: center;
          align-items: center;
          gap: 8px;
          margin-bottom: 24px;
        }

        .progress-container {
          margin-bottom: 20px;
        }

        .progress-track {
          height: 8px;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 4px;
          overflow: hidden;
        }

        .progress-fill {
          height: 100%;
          background: linear-gradient(90deg, #6366f1, #8b5cf6);
          border-radius: 4px;
        }

        .progress-label {
          display: block;
          text-align: center;
          font-size: 11px;
          color: #6b7280;
          margin-top: 4px;
        }

        /* VDF Progress */
        .vdf-progress {
          background: rgba(255, 193, 7, 0.1);
          border: 1px solid rgba(255, 193, 7, 0.3);
          border-radius: 12px;
          padding: 16px;
          margin-bottom: 16px;
        }

        .vdf-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 12px;
        }

        .vdf-icon {
          font-size: 18px;
        }

        .vdf-title {
          flex: 1;
          color: #ffc107;
          font-weight: 600;
          font-size: 14px;
        }

        .vdf-percent {
          color: #fff;
          font-family: monospace;
        }

        .vdf-bar {
          height: 6px;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 3px;
          overflow: hidden;
        }

        .vdf-fill {
          height: 100%;
          background: linear-gradient(90deg, #ffc107, #ff9800);
          transition: width 0.3s ease;
        }

        .vdf-eta {
          display: block;
          text-align: right;
          font-size: 11px;
          color: #9ca3af;
          margin-top: 6px;
        }

        /* Will Status */
        .will-status,
        .escrow-status {
          background: rgba(0, 0, 0, 0.2);
          border-radius: 12px;
          padding: 16px;
          margin-bottom: 16px;
        }

        .status-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 12px;
        }

        .status-icon {
          font-size: 18px;
        }

        .status-title {
          color: #e5e7eb;
          font-weight: 600;
          font-size: 14px;
        }

        .status-content {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .status-item {
          display: flex;
          justify-content: space-between;
          font-size: 13px;
          color: #9ca3af;
        }

        .status-item strong {
          color: #fff;
        }

        /* Escrow */
        .approval-meter {
          margin-bottom: 12px;
        }

        .approval-bar {
          height: 8px;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 4px;
          overflow: hidden;
        }

        .approval-fill {
          height: 100%;
          background: linear-gradient(90deg, #10b981, #059669);
        }

        .approval-text {
          display: block;
          text-align: center;
          font-size: 12px;
          color: #9ca3af;
          margin-top: 6px;
        }

        .condition-badge {
          font-size: 12px;
          color: #10b981;
          text-transform: capitalize;
        }

        /* Beneficiaries */
        .beneficiaries-section {
          margin-bottom: 16px;
        }

        .beneficiaries-toggle {
          width: 100%;
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px;
          background: rgba(79, 172, 254, 0.1);
          border: 1px solid rgba(79, 172, 254, 0.2);
          border-radius: 8px;
          color: #4facfe;
          cursor: pointer;
          font-size: 14px;
        }

        .beneficiaries-list {
          overflow: hidden;
          margin-top: 8px;
        }

        .beneficiary-item {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 10px;
          background: rgba(0, 0, 0, 0.2);
          border-radius: 8px;
          margin-bottom: 6px;
        }

        .ben-avatar {
          width: 32px;
          height: 32px;
          background: linear-gradient(135deg, #667eea, #764ba2);
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #fff;
          font-weight: 600;
          font-size: 14px;
        }

        .ben-info {
          flex: 1;
        }

        .ben-name {
          display: block;
          color: #e5e7eb;
          font-size: 13px;
        }

        .ben-email {
          display: block;
          color: #6b7280;
          font-size: 11px;
        }

        .ben-status {
          width: 24px;
          height: 24px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 50%;
          font-size: 12px;
        }

        .ben-status.verified {
          background: rgba(34, 197, 94, 0.2);
          color: #22c55e;
        }

        .ben-status.pending {
          background: rgba(255, 193, 7, 0.2);
          color: #ffc107;
        }

        .capsule-details {
          background: rgba(0, 0, 0, 0.2);
          border-radius: 8px;
          padding: 12px;
        }

        .detail-item {
          display: flex;
          justify-content: space-between;
          font-size: 12px;
          padding: 4px 0;
        }

        .detail-label {
          color: #6b7280;
        }

        .detail-value {
          color: #e5e7eb;
          font-family: 'Monaco', 'Consolas', monospace;
        }

        .mode-badge {
          font-family: inherit;
        }

        .loading {
          text-align: center;
          padding: 40px;
        }

        .spinner {
          width: 32px;
          height: 32px;
          border: 3px solid rgba(255,255,255,0.1);
          border-top-color: #6366f1;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin: 0 auto 12px;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

// Time unit component
const TimeUnit = ({ value, label }) => (
  <div className="time-unit">
    <motion.div
      className="time-value"
      key={value}
      initial={{ y: -10, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      {String(value).padStart(2, '0')}
    </motion.div>
    <div className="time-label">{label}</div>

    <style jsx>{`
      .time-unit {
        text-align: center;
        min-width: 60px;
      }

      .time-value {
        font-size: 36px;
        font-weight: 700;
        color: #fff;
        font-family: 'Monaco', 'Consolas', monospace;
        background: rgba(99, 102, 241, 0.2);
        border-radius: 8px;
        padding: 8px 12px;
      }

      .time-label {
        font-size: 11px;
        color: #9ca3af;
        text-transform: uppercase;
        margin-top: 4px;
      }
    `}</style>
  </div>
);

// Separator between time units
const Separator = () => (
  <div className="separator">
    <span>:</span>
    <style jsx>{`
      .separator {
        font-size: 28px;
        color: #6366f1;
        font-weight: 700;
        margin-top: -20px;
      }
    `}</style>
  </div>
);

export default TimeLockCountdown;

