/**
 * DNA Sequence Visualizer
 * =======================
 * 
 * Visual representation of encoded DNA sequences with:
 * - Nucleotide color coding (A=green, T=red, G=blue, C=yellow)
 * - GC content meter
 * - Sequence statistics
 * - Copy and export functionality
 */

import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import chemicalStorageService from '../../services/chemicalStorageService';

// Nucleotide colors
const NUCLEOTIDE_COLORS = {
    A: { bg: '#22c55e', text: '#ffffff', name: 'Adenine' },
    T: { bg: '#ef4444', text: '#ffffff', name: 'Thymine' },
    G: { bg: '#3b82f6', text: '#ffffff', name: 'Guanine' },
    C: { bg: '#eab308', text: '#000000', name: 'Cytosine' },
    N: { bg: '#6b7280', text: '#ffffff', name: 'Unknown' },
};

const DNASequenceVisualizer = ({
    sequence,
    gcContent,
    checksum,
    showControls = true,
    maxDisplayLength = 500,
}) => {
    const [copied, setCopied] = useState(false);
    const [viewMode, setViewMode] = useState('colored'); // 'colored', 'text', 'grouped'

    // Parse sequence statistics
    const stats = useMemo(() => {
        if (!sequence) return null;

        const counts = { A: 0, T: 0, G: 0, C: 0 };
        for (const char of sequence) {
            if (counts[char] !== undefined) counts[char]++;
        }

        const total = sequence.length;
        const gc = ((counts.G + counts.C) / total * 100).toFixed(1);

        return {
            length: total,
            counts,
            gcContent: gc,
            basePairs: Math.floor(total / 2),
        };
    }, [sequence]);

    // Copy to clipboard
    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(sequence);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error('Copy failed:', err);
        }
    };

    // Download as FASTA
    const handleDownload = () => {
        const fasta = `>PasswordStorage_${checksum?.slice(0, 8) || 'sequence'}\n${sequence}`;
        const blob = new Blob([fasta], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `dna_password_${Date.now()}.fasta`;
        a.click();
        URL.revokeObjectURL(url);
    };

    if (!sequence) {
        return (
            <div className="dna-visualizer-empty">
                <p>No DNA sequence to display</p>
            </div>
        );
    }

    // Truncate for display
    const displaySequence = sequence.length > maxDisplayLength
        ? sequence.slice(0, maxDisplayLength) + '...'
        : sequence;

    return (
        <div className="dna-visualizer">
            {/* Header with stats */}
            <div className="dna-visualizer-header">
                <div className="dna-stats">
                    <div className="stat">
                        <span className="label">Length</span>
                        <span className="value">{stats?.length} bp</span>
                    </div>
                    <div className="stat">
                        <span className="label">GC Content</span>
                        <span className="value" style={{
                            color: parseFloat(stats?.gcContent) >= 40 && parseFloat(stats?.gcContent) <= 60
                                ? '#22c55e'
                                : '#f59e0b'
                        }}>
                            {stats?.gcContent}%
                        </span>
                    </div>
                    {checksum && (
                        <div className="stat">
                            <span className="label">Checksum</span>
                            <span className="value mono">{checksum.slice(0, 8)}</span>
                        </div>
                    )}
                </div>

                {showControls && (
                    <div className="dna-controls">
                        <select
                            value={viewMode}
                            onChange={(e) => setViewMode(e.target.value)}
                            className="view-mode-select"
                        >
                            <option value="colored">Colored View</option>
                            <option value="text">Text View</option>
                            <option value="grouped">Grouped (10bp)</option>
                        </select>
                        <button onClick={handleCopy} className="btn-icon" title="Copy sequence">
                            {copied ? '✓' : '📋'}
                        </button>
                        <button onClick={handleDownload} className="btn-icon" title="Download FASTA">
                            💾
                        </button>
                    </div>
                )}
            </div>

            {/* GC Content Bar */}
            <div className="gc-content-bar">
                <div className="gc-bar-track">
                    <div
                        className="gc-bar-fill"
                        style={{
                            width: `${stats?.gcContent}%`,
                            backgroundColor: parseFloat(stats?.gcContent) >= 40 && parseFloat(stats?.gcContent) <= 60
                                ? '#22c55e'
                                : '#f59e0b'
                        }}
                    />
                    <div className="gc-bar-optimal" style={{ left: '40%', width: '20%' }} />
                </div>
                <div className="gc-labels">
                    <span>0%</span>
                    <span className="optimal-label">Optimal (40-60%)</span>
                    <span>100%</span>
                </div>
            </div>

            {/* Nucleotide Legend */}
            <div className="nucleotide-legend">
                {Object.entries(NUCLEOTIDE_COLORS).filter(([k]) => k !== 'N').map(([nucleotide, colors]) => (
                    <div key={nucleotide} className="legend-item">
                        <span
                            className="legend-dot"
                            style={{ backgroundColor: colors.bg }}
                        />
                        <span className="legend-label">{nucleotide}</span>
                        <span className="legend-count">{stats?.counts[nucleotide] || 0}</span>
                    </div>
                ))}
            </div>

            {/* Sequence Display */}
            <div className={`sequence-display mode-${viewMode}`}>
                {viewMode === 'colored' && (
                    <div className="colored-sequence">
                        {displaySequence.split('').map((nucleotide, index) => (
                            <span
                                key={index}
                                className="nucleotide"
                                style={{
                                    backgroundColor: NUCLEOTIDE_COLORS[nucleotide]?.bg || NUCLEOTIDE_COLORS.N.bg,
                                    color: NUCLEOTIDE_COLORS[nucleotide]?.text || NUCLEOTIDE_COLORS.N.text,
                                }}
                                title={NUCLEOTIDE_COLORS[nucleotide]?.name || 'Unknown'}
                            >
                                {nucleotide}
                            </span>
                        ))}
                    </div>
                )}

                {viewMode === 'text' && (
                    <pre className="text-sequence">{displaySequence}</pre>
                )}

                {viewMode === 'grouped' && (
                    <div className="grouped-sequence">
                        {displaySequence.match(/.{1,10}/g)?.map((group, index) => (
                            <span key={index} className="sequence-group">
                                <span className="group-number">{(index * 10 + 1).toString().padStart(4, '0')}</span>
                                {group}
                            </span>
                        ))}
                    </div>
                )}
            </div>

            {sequence.length > maxDisplayLength && (
                <div className="truncation-notice">
                    Showing first {maxDisplayLength} of {sequence.length} nucleotides
                </div>
            )}

            <style jsx>{`
        .dna-visualizer {
          background: var(--bg-secondary, #1a1a2e);
          border-radius: 12px;
          padding: 16px;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }

        .dna-visualizer-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
        }

        .dna-stats {
          display: flex;
          gap: 20px;
        }

        .stat {
          display: flex;
          flex-direction: column;
        }

        .stat .label {
          font-size: 11px;
          color: #9ca3af;
          text-transform: uppercase;
        }

        .stat .value {
          font-size: 18px;
          font-weight: 600;
          color: #fff;
        }

        .stat .value.mono {
          font-family: 'Monaco', 'Consolas', monospace;
          font-size: 14px;
        }

        .dna-controls {
          display: flex;
          gap: 8px;
        }

        .view-mode-select {
          background: rgba(255,255,255,0.1);
          border: 1px solid rgba(255,255,255,0.2);
          color: #fff;
          padding: 6px 12px;
          border-radius: 6px;
          font-size: 12px;
        }

        .btn-icon {
          background: rgba(255,255,255,0.1);
          border: none;
          padding: 8px;
          border-radius: 6px;
          cursor: pointer;
          font-size: 16px;
        }

        .btn-icon:hover {
          background: rgba(255,255,255,0.2);
        }

        .gc-content-bar {
          margin-bottom: 16px;
        }

        .gc-bar-track {
          position: relative;
          height: 12px;
          background: rgba(255,255,255,0.1);
          border-radius: 6px;
          overflow: hidden;
        }

        .gc-bar-fill {
          height: 100%;
          border-radius: 6px;
          transition: width 0.5s ease;
        }

        .gc-bar-optimal {
          position: absolute;
          top: 0;
          height: 100%;
          background: rgba(34, 197, 94, 0.2);
          border-left: 2px solid rgba(34, 197, 94, 0.5);
          border-right: 2px solid rgba(34, 197, 94, 0.5);
        }

        .gc-labels {
          display: flex;
          justify-content: space-between;
          font-size: 10px;
          color: #6b7280;
          margin-top: 4px;
        }

        .optimal-label {
          color: #22c55e;
        }

        .nucleotide-legend {
          display: flex;
          gap: 16px;
          margin-bottom: 16px;
          flex-wrap: wrap;
        }

        .legend-item {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
        }

        .legend-dot {
          width: 12px;
          height: 12px;
          border-radius: 3px;
        }

        .legend-label {
          color: #fff;
          font-weight: 600;
        }

        .legend-count {
          color: #9ca3af;
        }

        .sequence-display {
          background: rgba(0, 0, 0, 0.3);
          border-radius: 8px;
          padding: 12px;
          overflow-x: auto;
          max-height: 300px;
          overflow-y: auto;
        }

        .colored-sequence {
          display: flex;
          flex-wrap: wrap;
          gap: 1px;
          font-family: 'Monaco', 'Consolas', monospace;
          font-size: 11px;
        }

        .nucleotide {
          width: 14px;
          height: 18px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 2px;
          font-weight: 600;
        }

        .text-sequence {
          font-family: 'Monaco', 'Consolas', monospace;
          font-size: 12px;
          color: #e5e7eb;
          white-space: pre-wrap;
          word-break: break-all;
          margin: 0;
        }

        .grouped-sequence {
          display: flex;
          flex-direction: column;
          gap: 4px;
          font-family: 'Monaco', 'Consolas', monospace;
          font-size: 12px;
        }

        .sequence-group {
          display: flex;
          align-items: center;
          gap: 8px;
          color: #e5e7eb;
        }

        .group-number {
          color: #6b7280;
          font-size: 10px;
          min-width: 40px;
        }

        .truncation-notice {
          text-align: center;
          font-size: 11px;
          color: #6b7280;
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid rgba(255,255,255,0.1);
        }
      `}</style>
        </div>
    );
};

export default DNASequenceVisualizer;
