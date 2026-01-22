/**
 * VDFProgressTracker Component
 * 
 * Tracks client-side VDF (Verifiable Delay Function) computation progress.
 * Shows real-time progress, time estimates, and verification status.
 */

import React, { useState, useEffect, useRef } from 'react';
import './VDFProgressTracker.css';

const VDFProgressTracker = ({
    puzzleParams,  // { n, a, t } - modulus, base, iterations
    onComplete,
    onCancel,
    autoStart = false
}) => {
    const [status, setStatus] = useState('idle'); // idle, computing, verifying, complete, error
    const [progress, setProgress] = useState(0);
    const [iterationsDone, setIterationsDone] = useState(0);
    const [elapsedTime, setElapsedTime] = useState(0);
    const [estimatedRemaining, setEstimatedRemaining] = useState(null);
    const [result, setResult] = useState(null);

    const workerRef = useRef(null);
    const startTimeRef = useRef(null);
    const timerRef = useRef(null);

    useEffect(() => {
        if (autoStart && puzzleParams) {
            startComputation();
        }

        return () => {
            if (workerRef.current) {
                workerRef.current.terminate();
            }
            if (timerRef.current) {
                clearInterval(timerRef.current);
            }
        };
    }, [autoStart, puzzleParams]);

    const startComputation = () => {
        if (!puzzleParams) return;

        setStatus('computing');
        setProgress(0);
        setIterationsDone(0);
        startTimeRef.current = Date.now();

        // Timer for elapsed time
        timerRef.current = setInterval(() => {
            setElapsedTime(Math.floor((Date.now() - startTimeRef.current) / 1000));
        }, 1000);

        // Use Web Worker for computation (fallback to main thread)
        if (window.Worker) {
            const workerCode = `
        self.onmessage = function(e) {
          const { n, a, t } = e.data;
          const modulus = BigInt(n);
          let result = BigInt(a);
          const total = parseInt(t);
          const reportInterval = Math.max(1, Math.floor(total / 100));
          
          for (let i = 0; i < total; i++) {
            result = (result * result) % modulus;
            
            if (i % reportInterval === 0) {
              self.postMessage({ 
                type: 'progress', 
                progress: (i / total) * 100,
                iterations: i 
              });
            }
          }
          
          self.postMessage({ 
            type: 'complete', 
            output: result.toString() 
          });
        };
      `;

            const blob = new Blob([workerCode], { type: 'application/javascript' });
            workerRef.current = new Worker(URL.createObjectURL(blob));

            workerRef.current.onmessage = (e) => {
                if (e.data.type === 'progress') {
                    setProgress(e.data.progress);
                    setIterationsDone(e.data.iterations);
                    updateEstimate(e.data.progress);
                } else if (e.data.type === 'complete') {
                    handleComplete(e.data.output);
                }
            };

            workerRef.current.onerror = (err) => {
                setStatus('error');
                console.error('VDF Worker error:', err);
            };

            workerRef.current.postMessage(puzzleParams);
        } else {
            // Fallback: compute in chunks on main thread
            computeOnMainThread();
        }
    };

    const computeOnMainThread = async () => {
        const { n, a, t } = puzzleParams;
        const modulus = BigInt(n);
        let result = BigInt(a);
        const total = parseInt(t);
        const chunkSize = 1000;

        for (let i = 0; i < total; i += chunkSize) {
            const end = Math.min(i + chunkSize, total);
            for (let j = i; j < end; j++) {
                result = (result * result) % modulus;
            }

            setProgress((end / total) * 100);
            setIterationsDone(end);
            updateEstimate((end / total) * 100);

            // Yield to UI
            await new Promise(resolve => setTimeout(resolve, 0));
        }

        handleComplete(result.toString());
    };

    const updateEstimate = (currentProgress) => {
        if (currentProgress < 1) return;

        const elapsed = (Date.now() - startTimeRef.current) / 1000;
        const rate = currentProgress / elapsed;
        const remaining = (100 - currentProgress) / rate;

        setEstimatedRemaining(Math.ceil(remaining));
    };

    const handleComplete = (output) => {
        clearInterval(timerRef.current);
        setProgress(100);
        setStatus('complete');
        setResult(output);

        const totalTime = (Date.now() - startTimeRef.current) / 1000;

        onComplete?.({
            output,
            computationTime: totalTime,
            iterations: puzzleParams.t
        });
    };

    const handleCancel = () => {
        if (workerRef.current) {
            workerRef.current.terminate();
        }
        clearInterval(timerRef.current);
        setStatus('idle');
        setProgress(0);
        onCancel?.();
    };

    const formatTime = (seconds) => {
        if (!seconds || seconds < 0) return '--:--';
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    };

    const formatNumber = (num) => {
        if (!num) return '0';
        return num.toLocaleString();
    };

    return (
        <div className={`vdf-progress-tracker ${status}`}>
            <div className="tracker-header">
                <div className="icon">
                    {status === 'idle' && '⏸️'}
                    {status === 'computing' && '⚡'}
                    {status === 'verifying' && '🔍'}
                    {status === 'complete' && '✅'}
                    {status === 'error' && '❌'}
                </div>
                <div className="title">
                    <h3>VDF Computation</h3>
                    <p className="status-text">
                        {status === 'idle' && 'Ready to start'}
                        {status === 'computing' && 'Computing proof...'}
                        {status === 'verifying' && 'Verifying...'}
                        {status === 'complete' && 'Computation complete!'}
                        {status === 'error' && 'Error occurred'}
                    </p>
                </div>
            </div>

            <div className="progress-section">
                <div className="progress-bar">
                    <div
                        className="progress-fill"
                        style={{ width: `${progress}%` }}
                    />
                </div>
                <div className="progress-label">
                    {progress.toFixed(1)}%
                </div>
            </div>

            <div className="stats-grid">
                <div className="stat">
                    <span className="stat-value">{formatNumber(iterationsDone)}</span>
                    <span className="stat-label">Iterations</span>
                </div>
                <div className="stat">
                    <span className="stat-value">{formatTime(elapsedTime)}</span>
                    <span className="stat-label">Elapsed</span>
                </div>
                <div className="stat">
                    <span className="stat-value">{formatTime(estimatedRemaining)}</span>
                    <span className="stat-label">Remaining</span>
                </div>
                <div className="stat">
                    <span className="stat-value">
                        {elapsedTime > 0 ? Math.floor(iterationsDone / elapsedTime).toLocaleString() : '--'}
                    </span>
                    <span className="stat-label">Iter/sec</span>
                </div>
            </div>

            {puzzleParams && (
                <div className="params-info">
                    <details>
                        <summary>Technical Details</summary>
                        <div className="params-grid">
                            <div><span>Modulus bits:</span> {puzzleParams.n?.length * 3 || '?'}</div>
                            <div><span>Target iterations:</span> {formatNumber(parseInt(puzzleParams.t))}</div>
                            <div><span>Algorithm:</span> Wesolowski VDF</div>
                        </div>
                    </details>
                </div>
            )}

            <div className="tracker-actions">
                {status === 'idle' && (
                    <button className="btn start" onClick={startComputation}>
                        ▶️ Start Computation
                    </button>
                )}
                {status === 'computing' && (
                    <button className="btn cancel" onClick={handleCancel}>
                        ⏹️ Cancel
                    </button>
                )}
                {status === 'complete' && (
                    <button className="btn verify" onClick={() => setStatus('idle')}>
                        🔄 Reset
                    </button>
                )}
            </div>

            {status === 'computing' && (
                <div className="warning-banner">
                    ⚠️ Keep this tab open. Closing will cancel the computation.
                </div>
            )}
        </div>
    );
};

export default VDFProgressTracker;
