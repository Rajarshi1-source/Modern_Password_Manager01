/**
 * Anonymous Vault Access Component
 * ==================================
 * 
 * Wrapper component that routes vault operations through the Dark Protocol network.
 * Provides seamless integration with existing vault UI components.
 * 
 * @author Password Manager Team
 * @created 2026-02-02
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import darkProtocolService from '../../services/darkProtocolService';
import './AnonymousVaultAccess.css';

const AnonymousVaultAccess = ({ children }) => {
    const [isEnabled, setIsEnabled] = useState(false);
    const [isConnected, setIsConnected] = useState(false);
    const [isConnecting, setIsConnecting] = useState(false);
    const [session, setSession] = useState(null);
    const [stats, setStats] = useState({ operations: 0, bytesTransferred: 0 });
    const [error, setError] = useState(null);
    const [showStatus, setShowStatus] = useState(false);

    const pendingOperations = useRef(new Map());

    useEffect(() => {
        // Load config and check if enabled
        loadConfig();

        // Listen for connection events
        const unsubscribe = darkProtocolService.addConnectionListener(handleConnectionEvent);

        return () => {
            unsubscribe();
            if (isConnected) {
                darkProtocolService.disconnectWebSocket();
            }
        };
    }, []);

    const loadConfig = async () => {
        try {
            const config = await darkProtocolService.getConfig();
            setIsEnabled(config.is_enabled);

            // Check for existing session
            const sessionData = await darkProtocolService.getSession();
            if (sessionData.has_active_session) {
                setSession(sessionData);
                setIsConnected(true);
            }
        } catch (err) {
            console.error('Failed to load dark protocol config:', err);
        }
    };

    const handleConnectionEvent = useCallback((event) => {
        switch (event.type) {
            case 'connected':
                setIsConnected(true);
                setIsConnecting(false);
                break;
            case 'disconnected':
                setIsConnected(false);
                setIsConnecting(false);
                setSession(null);
                break;
            case 'session_expired':
                setIsConnected(false);
                setSession(null);
                setError('Session expired. Reconnecting...');
                break;
            case 'response':
                handleOperationResponse(event);
                break;
            default:
                break;
        }
    }, []);

    const handleOperationResponse = (event) => {
        const { bundleId, data } = event;
        const pending = pendingOperations.current.get(bundleId);
        if (pending) {
            pending.resolve(data);
            pendingOperations.current.delete(bundleId);
            setStats(prev => ({
                operations: prev.operations + 1,
                bytesTransferred: prev.bytesTransferred + (data?.size || 0),
            }));
        }
    };

    const connect = async () => {
        if (isConnected || isConnecting) return;

        setIsConnecting(true);
        setError(null);

        try {
            const newSession = await darkProtocolService.establishSession();
            setSession(newSession);
            setIsConnected(true);

            // Start cover traffic if enabled
            const config = await darkProtocolService.getConfig();
            if (config.cover_traffic_enabled) {
                darkProtocolService.startCoverTraffic(config.cover_traffic_intensity);
            }
        } catch (err) {
            setError(err.message);
            setIsConnecting(false);
        }
    };

    const disconnect = async () => {
        try {
            await darkProtocolService.terminateSession();
            setSession(null);
            setIsConnected(false);
            setStats({ operations: 0, bytesTransferred: 0 });
        } catch (err) {
            setError(err.message);
        }
    };

    const toggleAnonymous = async () => {
        if (isConnected) {
            await disconnect();
        } else {
            await connect();
        }
    };

    /**
     * Proxy a vault operation through the Dark Protocol network
     */
    const proxyOperation = async (operation, payload) => {
        if (!isConnected) {
            throw new Error('Dark Protocol not connected');
        }

        return darkProtocolService.proxyVaultOperation(operation, payload, session?.session_id);
    };

    // Expose proxyOperation to children via context or render prop
    const contextValue = {
        isEnabled,
        isConnected,
        isConnecting,
        session,
        proxyOperation,
        connect,
        disconnect,
    };

    return (
        <div className="anonymous-vault-wrapper">
            {/* Floating Status Indicator */}
            <div
                className={`ava-indicator ${isConnected ? 'connected' : ''}`}
                onClick={() => setShowStatus(!showStatus)}
                title={isConnected ? 'Anonymous mode active' : 'Standard connection'}
            >
                <span className="ava-icon">{isConnected ? '🌑' : '🔓'}</span>
                <div className="ava-pulse"></div>
            </div>

            {/* Status Panel */}
            {showStatus && (
                <div className="ava-status-panel">
                    <div className="ava-status-header">
                        <h4>Dark Protocol</h4>
                        <button
                            className="ava-close"
                            onClick={() => setShowStatus(false)}
                        >
                            ×
                        </button>
                    </div>

                    <div className="ava-status-body">
                        <div className={`ava-connection-status ${isConnected ? 'active' : ''}`}>
                            <div className="ava-status-dot"></div>
                            <span>
                                {isConnecting ? 'Connecting...' : isConnected ? 'Protected' : 'Standard'}
                            </span>
                        </div>

                        {isConnected && session && (
                            <div className="ava-session-info">
                                <div className="ava-info-row">
                                    <span className="ava-label">Session</span>
                                    <span className="ava-value">{session.session_id?.slice(0, 8)}...</span>
                                </div>
                                <div className="ava-info-row">
                                    <span className="ava-label">Path</span>
                                    <span className="ava-value">{session.path_length} hops</span>
                                </div>
                                <div className="ava-info-row">
                                    <span className="ava-label">Operations</span>
                                    <span className="ava-value">{stats.operations}</span>
                                </div>
                            </div>
                        )}

                        {error && (
                            <div className="ava-error">
                                {error}
                            </div>
                        )}
                    </div>

                    <div className="ava-status-footer">
                        <button
                            className={`ava-toggle-btn ${isConnected ? 'disconnect' : 'connect'}`}
                            onClick={toggleAnonymous}
                            disabled={isConnecting}
                        >
                            {isConnecting ? 'Connecting...' : isConnected ? 'Disconnect' : 'Go Anonymous'}
                        </button>
                    </div>
                </div>
            )}

            {/* Render children with context */}
            {typeof children === 'function'
                ? children(contextValue)
                : children
            }
        </div>
    );
};

/**
 * Hook for using anonymous vault access in child components
 */
export const useAnonymousVault = () => {
    const [proxyFn, setProxyFn] = useState(null);

    return {
        proxyOperation: proxyFn,
        isAnonymous: !!proxyFn,
    };
};

export default AnonymousVaultAccess;
