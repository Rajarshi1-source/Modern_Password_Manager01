/**
 * What-If Scenario Simulator
 * ============================
 * Interactive panel for running "what if" scenario simulations.
 */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { GitBranch, Play, Lightbulb, ArrowDown, History } from 'lucide-react';
import archaeologyService from '../../services/archaeologyService';

const SCENARIO_TYPES = [
    { value: 'earlier_change', label: 'Changed Password Earlier' },
    { value: 'stronger_password', label: 'Used Stronger Password' },
    { value: 'no_reuse', label: 'Avoided Password Reuse' },
    { value: 'regular_rotation', label: 'Regular Rotation Schedule' },
];

function RiskGauge({ value, label, color }) {
    return (
        <motion.div
            className="arch-risk-gauge"
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.5, type: 'spring' }}
        >
            <div
                className="arch-risk-gauge-value"
                style={{ color }}
            >
                {value}
            </div>
            <div className="arch-risk-gauge-label">{label}</div>
        </motion.div>
    );
}

export default function WhatIfSimulator() {
    const [scenarioType, setScenarioType] = useState('earlier_change');
    const [credentialDomain, setCredentialDomain] = useState('');
    const [daysEarlier, setDaysEarlier] = useState(30);
    const [targetStrength, setTargetStrength] = useState(90);
    const [rotationDays, setRotationDays] = useState(90);
    const [result, setResult] = useState(null);
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(false);
    const [showHistory, setShowHistory] = useState(false);

    useEffect(() => {
        (async () => {
            try {
                const h = await archaeologyService.getWhatIfHistory();
                setHistory(h.scenarios || []);
            } catch (err) {
                console.error('History error:', err);
            }
        })();
    }, []);

    const handleRun = async () => {
        setLoading(true);
        setResult(null);
        try {
            const params = {};
            if (scenarioType === 'earlier_change') params.days_earlier = daysEarlier;
            if (scenarioType === 'stronger_password') params.target_strength = targetStrength;
            if (scenarioType === 'regular_rotation') params.rotation_days = rotationDays;

            const res = await archaeologyService.runWhatIfScenario({
                scenario_type: scenarioType,
                credential_domain: credentialDomain,
                params,
            });
            setResult(res);
            // Refresh history
            const h = await archaeologyService.getWhatIfHistory();
            setHistory(h.scenarios || []);
        } catch (err) {
            console.error('What-if error:', err);
        } finally {
            setLoading(false);
        }
    };

    const getRiskColor = (score) => {
        if (score <= 20) return '#10b981';
        if (score <= 50) return '#f59e0b';
        return '#ef4444';
    };

    return (
        <div>
            <motion.div
                className="arch-whatif-panel"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
            >
                <h3 className="arch-chart-card-title" style={{ marginBottom: 20 }}>
                    <GitBranch size={20} />
                    What-If Scenario Simulator
                </h3>

                <div className="arch-whatif-form">
                    <div className="arch-form-group">
                        <label className="arch-form-label">Scenario Type</label>
                        <select
                            className="arch-form-select"
                            value={scenarioType}
                            onChange={(e) => setScenarioType(e.target.value)}
                        >
                            {SCENARIO_TYPES.map(t => (
                                <option key={t.value} value={t.value}>{t.label}</option>
                            ))}
                        </select>
                    </div>

                    <div className="arch-form-group">
                        <label className="arch-form-label">Credential Domain</label>
                        <input
                            className="arch-form-input"
                            type="text"
                            placeholder="e.g. google.com"
                            value={credentialDomain}
                            onChange={(e) => setCredentialDomain(e.target.value)}
                        />
                    </div>

                    {scenarioType === 'earlier_change' && (
                        <div className="arch-form-group">
                            <label className="arch-form-label">Days Earlier: {daysEarlier}</label>
                            <input
                                type="range"
                                min="7"
                                max="180"
                                value={daysEarlier}
                                onChange={(e) => setDaysEarlier(Number(e.target.value))}
                                className="arch-form-input"
                                style={{ padding: 0 }}
                            />
                        </div>
                    )}

                    {scenarioType === 'stronger_password' && (
                        <div className="arch-form-group">
                            <label className="arch-form-label">Target Strength: {targetStrength}</label>
                            <input
                                type="range"
                                min="50"
                                max="100"
                                value={targetStrength}
                                onChange={(e) => setTargetStrength(Number(e.target.value))}
                                className="arch-form-input"
                                style={{ padding: 0 }}
                            />
                        </div>
                    )}

                    {scenarioType === 'regular_rotation' && (
                        <div className="arch-form-group">
                            <label className="arch-form-label">Rotation Interval: {rotationDays} days</label>
                            <input
                                type="range"
                                min="30"
                                max="365"
                                value={rotationDays}
                                onChange={(e) => setRotationDays(Number(e.target.value))}
                                className="arch-form-input"
                                style={{ padding: 0 }}
                            />
                        </div>
                    )}

                    <div className="arch-form-group">
                        <label className="arch-form-label">&nbsp;</label>
                        <button
                            className="arch-btn-primary"
                            onClick={handleRun}
                            disabled={loading}
                        >
                            {loading ? (
                                <><div className="arch-loading-spinner" style={{ width: 16, height: 16 }} /> Running...</>
                            ) : (
                                <><Play size={16} /> Run Simulation</>
                            )}
                        </button>
                    </div>
                </div>

                {/* Results */}
                <AnimatePresence>
                    {result && (
                        <motion.div
                            className="arch-whatif-results"
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: 0.4 }}
                        >
                            <RiskGauge
                                value={result.actual_risk_score}
                                label="Actual Risk"
                                color={getRiskColor(result.actual_risk_score)}
                            />
                            <RiskGauge
                                value={result.simulated_risk_score}
                                label="Simulated Risk"
                                color={getRiskColor(result.simulated_risk_score)}
                            />
                            <RiskGauge
                                value={`-${result.risk_reduction}`}
                                label="Risk Reduction"
                                color="#10b981"
                            />
                            {result.insight_text && (
                                <div className="arch-whatif-insight">
                                    <Lightbulb size={16} style={{ display: 'inline', marginRight: 8, color: '#f59e0b' }} />
                                    <strong>Insight:</strong> {result.insight_text}
                                </div>
                            )}
                        </motion.div>
                    )}
                </AnimatePresence>
            </motion.div>

            {/* History */}
            {history.length > 0 && (
                <motion.div
                    style={{ marginTop: 20 }}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.3 }}
                >
                    <button
                        className="arch-tab"
                        onClick={() => setShowHistory(!showHistory)}
                        style={{ marginBottom: 12 }}
                    >
                        <History size={16} />
                        Past Simulations ({history.length})
                        {showHistory ? <ArrowDown size={14} style={{ transform: 'rotate(180deg)' }} /> : <ArrowDown size={14} />}
                    </button>

                    <AnimatePresence>
                        {showHistory && (
                            <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                            >
                                {history.slice(0, 10).map((s, i) => (
                                    <div key={s.id} className="arch-timeline-card" style={{ marginBottom: 8 }}>
                                        <div className="arch-timeline-card-header">
                                            <div className="arch-timeline-card-title">
                                                <GitBranch size={14} />
                                                {s.scenario_type_display}
                                                {s.credential_domain && ` — ${s.credential_domain}`}
                                            </div>
                                            <span className="arch-timeline-timestamp">
                                                {new Date(s.created_at).toLocaleDateString()}
                                            </span>
                                        </div>
                                        <div className="arch-timeline-card-body">
                                            Risk: {s.actual_risk_score} → {s.simulated_risk_score}
                                            (reduced by {s.risk_reduction})
                                        </div>
                                    </div>
                                ))}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </motion.div>
            )}
        </div>
    );
}
