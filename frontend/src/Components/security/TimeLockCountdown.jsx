/**
 * Time-Lock Countdown Component
 * =============================
 * 
 * Animated countdown timer for time-lock capsules.
 * Shows remaining time until password becomes accessible.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';

const TimeLockCountdown = ({
    unlockAt,
    onUnlocked,
    capsuleId,
    beneficiaryEmail,
    showDetails = true,
}) => {
    const [timeRemaining, setTimeRemaining] = useState(null);
    const [isUnlocked, setIsUnlocked] = useState(false);

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
        const created = new Date(unlockAt).getTime() - (timeRemaining.totalSeconds * 1000 + Date.now() - Date.now());
        // Simplified: just show based on remaining time
        return Math.max(0, 100 - (timeRemaining.totalSeconds / 259200) * 100); // 72 hours = 259200 seconds
    };

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
                </div>
            )}

            <style jsx>{`
        .timelock-countdown {
          background: linear-gradient(135deg, #1e1e3f 0%, #0f0f23 100%);
          border: 1px solid rgba(99, 102, 241, 0.3);
          border-radius: 16px;
          padding: 24px;
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
