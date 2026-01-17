/**
 * GeneticOAuthCallback Component
 * ================================
 * 
 * Handles OAuth callback from DNA providers (Sequencing.com, 23andMe).
 * This page receives the authorization code and posts it back to the parent window.
 * 
 * @author Password Manager Team
 * @created 2026-01-16
 */

import React, { useEffect, useState } from 'react';
import styled, { keyframes } from 'styled-components';
import geneticService from '../../services/geneticService';

// =============================================================================
// Animations
// =============================================================================

const helixRotate = keyframes`
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
`;

const pulse = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
`;

// =============================================================================
// Styled Components
// =============================================================================

const Container = styled.div`
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1F2937 0%, #111827 100%);
  padding: 20px;
`;

const Card = styled.div`
  background: rgba(255, 255, 255, 0.05);
  border-radius: 20px;
  padding: 40px;
  max-width: 400px;
  width: 100%;
  text-align: center;
  border: 1px solid rgba(16, 185, 129, 0.2);
`;

const Icon = styled.div`
  font-size: 64px;
  margin-bottom: 24px;
  
  ${props => props.$loading && `
    animation: ${helixRotate} 2s linear infinite;
  `}
`;

const Title = styled.h1`
  font-size: 24px;
  font-weight: 700;
  color: #fff;
  margin: 0 0 12px;
`;

const Subtitle = styled.p`
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
  margin: 0 0 24px;
  line-height: 1.6;
`;

const StatusMessage = styled.div`
  padding: 16px;
  border-radius: 12px;
  margin-top: 20px;
  
  ${props => props.$type === 'success' && `
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.3);
    color: #10B981;
  `}
  
  ${props => props.$type === 'error' && `
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #EF4444;
  `}
  
  ${props => props.$type === 'loading' && `
    background: rgba(59, 130, 246, 0.1);
    border: 1px solid rgba(59, 130, 246, 0.3);
    color: #3B82F6;
    animation: ${pulse} 1.5s ease-in-out infinite;
  `}
`;

const CloseButton = styled.button`
  margin-top: 24px;
  padding: 12px 32px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, #10B981, #059669);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    background: linear-gradient(135deg, #059669, #047857);
    transform: translateY(-1px);
  }
`;

// =============================================================================
// Component
// =============================================================================

const GeneticOAuthCallback = () => {
    const [status, setStatus] = useState('loading');
    const [message, setMessage] = useState('Processing your DNA connection...');
    const [result, setResult] = useState(null);

    useEffect(() => {
        handleCallback();
    }, []);

    const handleCallback = async () => {
        try {
            // Get URL parameters
            const urlParams = new URLSearchParams(window.location.search);
            const code = urlParams.get('code');
            const state = urlParams.get('state');
            const error = urlParams.get('error');
            const errorDescription = urlParams.get('error_description');

            // Check for OAuth error
            if (error) {
                throw new Error(errorDescription || `OAuth error: ${error}`);
            }

            // Validate required parameters
            if (!code || !state) {
                throw new Error('Missing authorization code or state parameter');
            }

            setMessage('Exchanging authorization code...');

            // Call backend to complete OAuth flow
            const callbackResult = await geneticService.handleOAuthCallback(code, state);

            setResult(callbackResult);
            setStatus('success');
            setMessage(`Successfully connected! Found ${callbackResult.snpCount?.toLocaleString() || 'many'} genetic markers.`);

            // Notify opener window
            if (window.opener && !window.opener.closed) {
                window.opener.postMessage({
                    type: 'genetic_oauth_callback',
                    success: true,
                    provider: callbackResult.provider,
                    snpCount: callbackResult.snpCount,
                    geneticHashPrefix: callbackResult.geneticHashPrefix,
                }, window.location.origin);

                // Auto-close after short delay
                setTimeout(() => {
                    window.close();
                }, 2000);
            }

        } catch (err) {
            console.error('OAuth callback error:', err);
            setStatus('error');
            setMessage(err.message || 'Failed to complete DNA connection');

            // Notify opener window of error
            if (window.opener && !window.opener.closed) {
                window.opener.postMessage({
                    type: 'genetic_oauth_callback',
                    success: false,
                    error: err.message,
                }, window.location.origin);
            }
        }
    };

    const handleClose = () => {
        window.close();
    };

    const getIcon = () => {
        switch (status) {
            case 'success':
                return '✅';
            case 'error':
                return '❌';
            default:
                return '🧬';
        }
    };

    const getTitle = () => {
        switch (status) {
            case 'success':
                return 'DNA Connected!';
            case 'error':
                return 'Connection Failed';
            default:
                return 'Connecting DNA...';
        }
    };

    return (
        <Container>
            <Card>
                <Icon $loading={status === 'loading'}>
                    {getIcon()}
                </Icon>

                <Title>{getTitle()}</Title>

                <Subtitle>
                    {status === 'loading'
                        ? 'Please wait while we securely process your genetic data connection.'
                        : status === 'success'
                            ? 'Your DNA has been connected. You can now generate bio-unique passwords.'
                            : 'There was a problem connecting your DNA. Please try again.'}
                </Subtitle>

                <StatusMessage $type={status}>
                    {message}
                </StatusMessage>

                {status !== 'loading' && (
                    <CloseButton onClick={handleClose}>
                        {status === 'success' ? 'Close Window' : 'Try Again'}
                    </CloseButton>
                )}

                {status === 'success' && result && (
                    <div style={{
                        marginTop: '16px',
                        fontSize: '12px',
                        color: 'rgba(255,255,255,0.4)',
                        fontFamily: 'monospace'
                    }}>
                        Hash: {result.geneticHashPrefix?.slice(0, 16)}...
                    </div>
                )}
            </Card>
        </Container>
    );
};

export default GeneticOAuthCallback;
