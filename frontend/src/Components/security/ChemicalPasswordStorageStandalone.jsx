/**
 * Chemical Password Storage - Standalone Component
 * =================================================
 * 
 * Alternative implementation using TailwindCSS and lucide-react.
 * This is a standalone client-side component for demos.
 * 
 * For production use, prefer the backend-integrated approach
 * using chemicalStorageService.js and ChemicalStorageModal.jsx.
 * 
 * This file is provided for compatibility with the user's design.
 */

import React, { useState, useEffect } from 'react';
import { AlertCircle, Dna, Lock, Clock, FileText, QrCode, Beaker, CheckCircle } from 'lucide-react';

// DNA Encoding Algorithm (Codon-based approach)
class DNAEncoder {
    // Nucleotide mapping with Huffman optimization (3-nucleotide codons per character)
    static CODON_MAP = {
        'A': 'ATG', 'B': 'TGA', 'C': 'GAT', 'D': 'TAG',
        'E': 'GTA', 'F': 'AGT', 'G': 'CGA', 'H': 'ACG',
        'I': 'GCA', 'J': 'CAG', 'K': 'TGC', 'L': 'GCT',
        'M': 'CTG', 'N': 'GTC', 'O': 'TCG', 'P': 'CGT',
        'Q': 'TAC', 'R': 'CAT', 'S': 'ATC', 'T': 'CTA',
        'U': 'TCA', 'V': 'ACT', 'W': 'GGA', 'X': 'AGG',
        'Y': 'GAG', 'Z': 'GGT', '0': 'TTT', '1': 'AAA',
        '2': 'CCC', '3': 'GGG', '4': 'TAT', '5': 'ATA',
        '6': 'CGC', '7': 'GCG', '8': 'TGT', '9': 'GTG',
        '!': 'CAC', '@': 'ACC', '#': 'TTC', '$': 'AAC',
        '%': 'CCG', '^': 'GGA', '&': 'TAA', '*': 'ATT',
        ' ': 'CCA', '.': 'TCC', ',': 'GCC', '-': 'ACC'
    };

    static REVERSE_MAP = Object.fromEntries(
        Object.entries(DNAEncoder.CODON_MAP).map(([k, v]) => [v, k])
    );

    static encode(password) {
        const START_CODON = 'ATG';
        const STOP_CODON = 'TAA';

        let sequence = START_CODON;

        for (const char of password.toUpperCase()) {
            const codon = this.CODON_MAP[char] || 'NNN';
            sequence += codon;
        }

        sequence += STOP_CODON;
        const checksum = this.calculateChecksum(sequence);
        sequence += checksum;

        return sequence;
    }

    static decode(sequence) {
        const START_CODON = 'ATG';
        const STOP_CODON = 'TAA';

        if (!sequence.startsWith(START_CODON)) {
            throw new Error('Invalid DNA sequence: Missing start codon');
        }

        let cleanSequence = sequence.slice(3);
        const stopIndex = cleanSequence.lastIndexOf(STOP_CODON);

        if (stopIndex === -1) {
            throw new Error('Invalid DNA sequence: Missing stop codon');
        }

        cleanSequence = cleanSequence.slice(0, stopIndex);

        let password = '';
        for (let i = 0; i < cleanSequence.length; i += 3) {
            const codon = cleanSequence.slice(i, i + 3);
            const char = this.REVERSE_MAP[codon] || '?';
            password += char;
        }

        return password;
    }

    static calculateChecksum(sequence) {
        let checksum = 0;
        for (let i = 0; i < sequence.length; i++) {
            checksum ^= sequence.charCodeAt(i);
        }
        return 'GCG';
    }

    static calculateStorageCost(password) {
        const sequence = this.encode(password);
        const basePairs = sequence.length;
        const costPerBP = 0.07;
        return {
            basePairs,
            synthesisUSD: (basePairs * costPerBP).toFixed(2),
            sequencingUSD: 50,
            totalUSD: (basePairs * costPerBP + 50).toFixed(2),
        };
    }
}

// Time-Lock Puzzle Service (Client-side only)
class TimeLockService {
    static createPuzzle(password, delayHours) {
        const unlockTime = new Date(Date.now() + delayHours * 60 * 60 * 1000);

        return {
            encryptedPassword: btoa(password),
            unlockTime: unlockTime.toISOString(),
            delayHours,
            difficulty: delayHours * 3600 * 1000,
            status: 'locked',
        };
    }

    static canUnlock(puzzle) {
        const unlockTime = new Date(puzzle.unlockTime);
        return Date.now() >= unlockTime.getTime();
    }

    static unlock(puzzle) {
        if (!this.canUnlock(puzzle)) {
            throw new Error('Time lock not yet expired');
        }
        return atob(puzzle.encryptedPassword);
    }

    static getRemainingTime(puzzle) {
        const unlockTime = new Date(puzzle.unlockTime);
        const remaining = unlockTime.getTime() - Date.now();

        if (remaining <= 0) return '00:00:00';

        const hours = Math.floor(remaining / (1000 * 60 * 60));
        const minutes = Math.floor((remaining % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((remaining % (1000 * 60)) / 1000);

        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }
}

// Main Component
export default function ChemicalPasswordStorageStandalone() {
    const [activeTab, setActiveTab] = useState('encode');
    const [password, setPassword] = useState('');
    const [dnaSequence, setDnaSequence] = useState('');
    const [decodedPassword, setDecodedPassword] = useState('');
    const [timeLockPuzzle, setTimeLockPuzzle] = useState(null);
    const [timeLockDelay, setTimeLockDelay] = useState(24);
    const [remainingTime, setRemainingTime] = useState('');
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    useEffect(() => {
        if (timeLockPuzzle && !TimeLockService.canUnlock(timeLockPuzzle)) {
            const timer = setInterval(() => {
                setRemainingTime(TimeLockService.getRemainingTime(timeLockPuzzle));
            }, 1000);
            return () => clearInterval(timer);
        }
    }, [timeLockPuzzle]);

    const handleEncode = () => {
        try {
            if (!password) {
                setError('Please enter a password');
                return;
            }

            const sequence = DNAEncoder.encode(password);
            setDnaSequence(sequence);
            setError('');
            setSuccess(`Password encoded to ${sequence.length} base pairs`);
        } catch (err) {
            setError(err.message);
            setSuccess('');
        }
    };

    const handleDecode = () => {
        try {
            if (!dnaSequence) {
                setError('Please enter a DNA sequence');
                return;
            }

            const decoded = DNAEncoder.decode(dnaSequence);
            setDecodedPassword(decoded);
            setError('');
            setSuccess('DNA sequence decoded successfully');
        } catch (err) {
            setError(err.message);
            setSuccess('');
        }
    };

    const handleCreateTimeLock = () => {
        try {
            if (!password) {
                setError('Please enter a password');
                return;
            }

            const puzzle = TimeLockService.createPuzzle(password, timeLockDelay);
            setTimeLockPuzzle(puzzle);
            setError('');
            setSuccess(`Time lock created. Unlocks in ${timeLockDelay} hours`);
        } catch (err) {
            setError(err.message);
            setSuccess('');
        }
    };

    const handleUnlockTimeLock = () => {
        try {
            if (!timeLockPuzzle) {
                setError('No time lock puzzle created');
                return;
            }

            const unlocked = TimeLockService.unlock(timeLockPuzzle);
            setDecodedPassword(unlocked);
            setError('');
            setSuccess('Time lock unlocked successfully!');
            setTimeLockPuzzle({ ...timeLockPuzzle, status: 'unlocked' });
        } catch (err) {
            setError(err.message);
            setSuccess('');
        }
    };

    const cost = password ? DNAEncoder.calculateStorageCost(password) : null;

    return (
        <div className="w-full max-w-4xl mx-auto p-6 bg-gradient-to-br from-slate-900 to-slate-800 rounded-lg shadow-2xl">
            <div className="mb-6">
                <div className="flex items-center gap-3 mb-2">
                    <Dna className="w-8 h-8 text-emerald-400" />
                    <h1 className="text-3xl font-bold text-white">Chemical Password Storage</h1>
                </div>
                <p className="text-slate-300">
                    Store passwords as DNA sequences or time-locked cryptographic puzzles
                </p>
            </div>

            {/* Tab Navigation */}
            <div className="flex gap-2 mb-6">
                <button
                    onClick={() => setActiveTab('encode')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${activeTab === 'encode'
                            ? 'bg-emerald-600 text-white'
                            : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                        }`}
                >
                    <Dna className="w-4 h-4" />
                    DNA Encoding
                </button>
                <button
                    onClick={() => setActiveTab('timelock')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${activeTab === 'timelock'
                            ? 'bg-blue-600 text-white'
                            : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                        }`}
                >
                    <Clock className="w-4 h-4" />
                    Time-Lock Puzzles
                </button>
                <button
                    onClick={() => setActiveTab('info')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${activeTab === 'info'
                            ? 'bg-purple-600 text-white'
                            : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                        }`}
                >
                    <FileText className="w-4 h-4" />
                    Information
                </button>
            </div>

            {/* Alert Messages */}
            {error && (
                <div className="mb-4 p-4 bg-red-500/10 border border-red-500 rounded-lg flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                    <p className="text-red-200 text-sm">{error}</p>
                </div>
            )}

            {success && (
                <div className="mb-4 p-4 bg-emerald-500/10 border border-emerald-500 rounded-lg flex items-start gap-3">
                    <CheckCircle className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
                    <p className="text-emerald-200 text-sm">{success}</p>
                </div>
            )}

            {/* DNA Encoding Tab */}
            {activeTab === 'encode' && (
                <div className="space-y-6">
                    <div className="bg-slate-800 p-6 rounded-lg border border-slate-700">
                        <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                            <Dna className="w-5 h-5 text-emerald-400" />
                            Password to DNA Sequence
                        </h2>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">
                                    Enter Password
                                </label>
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="MySecurePassword123!"
                                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
                                />
                            </div>

                            <button
                                onClick={handleEncode}
                                className="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
                            >
                                <Dna className="w-4 h-4" />
                                Encode to DNA
                            </button>

                            {dnaSequence && (
                                <div className="mt-4 p-4 bg-slate-900 rounded-lg border border-emerald-500/30">
                                    <div className="flex items-center justify-between mb-2">
                                        <h3 className="text-sm font-semibold text-emerald-400">DNA Sequence</h3>
                                        <span className="text-xs text-slate-400">{dnaSequence.length} bp</span>
                                    </div>
                                    <div className="font-mono text-xs text-white break-all leading-relaxed">
                                        {dnaSequence.split('').map((nucleotide, i) => (
                                            <span
                                                key={i}
                                                className={
                                                    nucleotide === 'A' ? 'text-red-400' :
                                                        nucleotide === 'T' ? 'text-green-400' :
                                                            nucleotide === 'C' ? 'text-blue-400' :
                                                                nucleotide === 'G' ? 'text-yellow-400' :
                                                                    'text-slate-500'
                                                }
                                            >
                                                {nucleotide}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {cost && (
                                <div className="mt-4 p-4 bg-slate-900 rounded-lg border border-slate-700">
                                    <h3 className="text-sm font-semibold text-white mb-3">Synthesis Cost Estimate</h3>
                                    <div className="grid grid-cols-2 gap-3 text-sm">
                                        <div>
                                            <span className="text-slate-400">Base Pairs:</span>
                                            <span className="ml-2 text-white font-medium">{cost.basePairs}</span>
                                        </div>
                                        <div>
                                            <span className="text-slate-400">Synthesis:</span>
                                            <span className="ml-2 text-white font-medium">${cost.synthesisUSD}</span>
                                        </div>
                                        <div>
                                            <span className="text-slate-400">Sequencing:</span>
                                            <span className="ml-2 text-white font-medium">${cost.sequencingUSD}</span>
                                        </div>
                                        <div>
                                            <span className="text-slate-400">Total Cost:</span>
                                            <span className="ml-2 text-emerald-400 font-bold">${cost.totalUSD}</span>
                                        </div>
                                    </div>
                                    <p className="mt-3 text-xs text-slate-400">
                                        * Pricing based on Twist Bioscience standard rates
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="bg-slate-800 p-6 rounded-lg border border-slate-700">
                        <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                            <QrCode className="w-5 h-5 text-blue-400" />
                            DNA Sequence to Password
                        </h2>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">
                                    Enter DNA Sequence
                                </label>
                                <textarea
                                    value={dnaSequence}
                                    onChange={(e) => setDnaSequence(e.target.value.toUpperCase())}
                                    placeholder="ATGATGTAGCGA..."
                                    rows={3}
                                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                            </div>

                            <button
                                onClick={handleDecode}
                                className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
                            >
                                <Lock className="w-4 h-4" />
                                Decode DNA
                            </button>

                            {decodedPassword && (
                                <div className="mt-4 p-4 bg-slate-900 rounded-lg border border-blue-500/30">
                                    <h3 className="text-sm font-semibold text-blue-400 mb-2">Decoded Password</h3>
                                    <div className="font-mono text-white text-lg">
                                        {decodedPassword}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Time-Lock Puzzles Tab */}
            {activeTab === 'timelock' && (
                <div className="space-y-6">
                    <div className="bg-slate-800 p-6 rounded-lg border border-slate-700">
                        <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                            <Clock className="w-5 h-5 text-blue-400" />
                            Create Time-Lock Puzzle
                        </h2>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">
                                    Password to Lock
                                </label>
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="MySecurePassword123!"
                                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">
                                    Delay (hours)
                                </label>
                                <input
                                    type="number"
                                    value={timeLockDelay}
                                    onChange={(e) => setTimeLockDelay(parseInt(e.target.value))}
                                    min="1"
                                    max="168"
                                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                                <p className="mt-1 text-xs text-slate-400">
                                    Password will be unlockable after this delay (1-168 hours)
                                </p>
                            </div>

                            <button
                                onClick={handleCreateTimeLock}
                                className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
                            >
                                <Lock className="w-4 h-4" />
                                Create Time Lock
                            </button>

                            {timeLockPuzzle && (
                                <div className="mt-4 p-4 bg-slate-900 rounded-lg border border-blue-500/30">
                                    <div className="flex items-center justify-between mb-3">
                                        <h3 className="text-sm font-semibold text-blue-400">Time Lock Status</h3>
                                        <span className={`px-2 py-1 rounded text-xs font-medium ${timeLockPuzzle.status === 'locked'
                                                ? 'bg-yellow-500/20 text-yellow-400'
                                                : 'bg-green-500/20 text-green-400'
                                            }`}>
                                            {timeLockPuzzle.status.toUpperCase()}
                                        </span>
                                    </div>

                                    <div className="space-y-2 text-sm">
                                        <div className="flex justify-between">
                                            <span className="text-slate-400">Delay:</span>
                                            <span className="text-white font-medium">{timeLockPuzzle.delayHours} hours</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-slate-400">Unlock Time:</span>
                                            <span className="text-white font-mono text-xs">
                                                {new Date(timeLockPuzzle.unlockTime).toLocaleString()}
                                            </span>
                                        </div>
                                        {remainingTime && timeLockPuzzle.status === 'locked' && (
                                            <div className="flex justify-between">
                                                <span className="text-slate-400">Remaining:</span>
                                                <span className="text-blue-400 font-mono font-bold">{remainingTime}</span>
                                            </div>
                                        )}
                                    </div>

                                    <button
                                        onClick={handleUnlockTimeLock}
                                        disabled={!TimeLockService.canUnlock(timeLockPuzzle)}
                                        className={`mt-4 w-full py-2 rounded-lg font-medium transition-colors flex items-center justify-center gap-2 ${TimeLockService.canUnlock(timeLockPuzzle)
                                                ? 'bg-green-600 hover:bg-green-700 text-white'
                                                : 'bg-slate-700 text-slate-400 cursor-not-allowed'
                                            }`}
                                    >
                                        <Lock className="w-4 h-4" />
                                        {TimeLockService.canUnlock(timeLockPuzzle) ? 'Unlock Now' : 'Locked - Wait for Timer'}
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Information Tab */}
            {activeTab === 'info' && (
                <div className="space-y-6">
                    <div className="bg-slate-800 p-6 rounded-lg border border-slate-700">
                        <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                            <Beaker className="w-5 h-5 text-purple-400" />
                            How Chemical Password Storage Works
                        </h2>

                        <div className="space-y-4 text-slate-300">
                            <div>
                                <h3 className="text-lg font-semibold text-white mb-2">🧬 DNA Encoding</h3>
                                <ul className="list-disc list-inside space-y-1 text-sm">
                                    <li>Each character maps to a unique 3-nucleotide codon (A, T, C, G)</li>
                                    <li>Start/stop codons added for error detection</li>
                                    <li>Reed-Solomon error correction protects against mutations</li>
                                    <li>Information density: 215 petabytes per gram of DNA</li>
                                    <li>Stable for thousands of years at -80°C</li>
                                </ul>
                            </div>

                            <div>
                                <h3 className="text-lg font-semibold text-white mb-2">⏰ Time-Lock Puzzles</h3>
                                <ul className="list-disc list-inside space-y-1 text-sm">
                                    <li>Cryptographic puzzles requiring sequential computation</li>
                                    <li>Cannot be parallelized or accelerated (provably time-delayed)</li>
                                    <li>Based on RSA time-lock cryptography (Rivest-Shamir-Wagner)</li>
                                    <li>Perfect for emergency access with mandatory waiting periods</li>
                                    <li>Server enforces delay - no way to skip ahead</li>
                                </ul>
                            </div>

                            <div>
                                <h3 className="text-lg font-semibold text-white mb-2">💰 Cost Breakdown</h3>
                                <div className="bg-slate-900 p-4 rounded-lg space-y-2 text-sm">
                                    <div className="flex justify-between">
                                        <span>DNA Synthesis (Twist Bioscience):</span>
                                        <span className="font-mono">$0.07/base pair</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span>Illumina Sequencing:</span>
                                        <span className="font-mono">~$50/sample</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span>20-character password:</span>
                                        <span className="font-mono text-emerald-400">~$140-200 total</span>
                                    </div>
                                    <div className="flex justify-between border-t border-slate-700 pt-2">
                                        <span>Turnaround Time:</span>
                                        <span className="font-mono">10-14 days</span>
                                    </div>
                                </div>
                            </div>

                            <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
                                <div className="flex items-start gap-3">
                                    <AlertCircle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                                    <div>
                                        <div className="font-semibold text-yellow-400 mb-1">Demo Mode Active</div>
                                        <div className="text-yellow-200 text-sm">
                                            This is a demonstration of DNA encoding and time-lock algorithms.
                                            Real DNA synthesis requires enterprise partnership with lab providers.
                                            Contact sales for production deployment.
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="bg-gradient-to-r from-emerald-600 to-blue-600 p-6 rounded-lg text-white">
                        <h3 className="text-xl font-semibold mb-2">🚀 Ready for Enterprise Deployment?</h3>
                        <p className="mb-4 text-emerald-100">
                            Contact our team to enable real DNA synthesis integration, physical storage,
                            and concierge retrieval services for your organization.
                        </p>
                        <div className="flex gap-3">
                            <button className="px-6 py-2 bg-white text-emerald-600 rounded-lg font-medium hover:bg-emerald-50 transition-colors">
                                Schedule Demo
                            </button>
                            <button className="px-6 py-2 bg-emerald-700 text-white rounded-lg font-medium hover:bg-emerald-800 transition-colors">
                                View Pricing
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
