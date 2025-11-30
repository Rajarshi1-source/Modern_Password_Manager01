import React, { useState, useRef, useEffect } from 'react';
import styled from 'styled-components';
import { FaCamera, FaMicrophone, FaFingerprint, FaCheck, FaTimes, FaSpinner } from 'react-icons/fa';
import mfaService from '../../services/mfaService';
import { errorTracker } from '../../services/errorTracker';
import Button from '../common/Button';

const Container = styled.div`
  max-width: 500px;
  margin: 0 auto;
  padding: 2rem;
`;

const AuthCard = styled.div`
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 2rem;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  text-align: center;
`;

const Title = styled.h3`
  margin-bottom: 1.5rem;
  color: var(--text-primary);
`;

const MethodSelector = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
`;

const MethodButton = styled.button`
  padding: 1.5rem 1rem;
  background: ${props => props.active ? 'var(--primary)' : 'var(--bg-primary)'};
  color: ${props => props.active ? 'white' : 'var(--text-primary)'};
  border: 2px solid ${props => props.active ? 'var(--primary)' : 'var(--border-color)'};
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  
  &:hover:not(:disabled) {
    border-color: var(--primary);
    transform: translateY(-2px);
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const VideoContainer = styled.div`
  position: relative;
  width: 100%;
  max-width: 320px;
  margin: 0 auto 1.5rem;
  border-radius: 8px;
  overflow: hidden;
  background: #000;
`;

const Video = styled.video`
  width: 100%;
  display: block;
`;

const Canvas = styled.canvas`
  display: none;
`;

const Message = styled.div`
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  justify-content: center;
  
  ${props => props.type === 'success' && `
    background: var(--success-light);
    color: var(--success);
  `}
  
  ${props => props.type === 'error' && `
    background: var(--danger-light);
    color: var(--danger);
  `}
  
  ${props => props.type === 'info' && `
    background: var(--primary-light);
    color: var(--primary);
  `}
`;

const RecordingIndicator = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 1rem;
  background: var(--danger);
  color: white;
  border-radius: 8px;
  margin-bottom: 1rem;
  
  .pulse-dot {
    width: 10px;
    height: 10px;
    background: white;
    border-radius: 50%;
    animation: pulse 1s infinite;
  }
  
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
`;

const BiometricAuth = ({ requiredFactors, onSuccess, onCancel }) => {
  const [selectedMethod, setSelectedMethod] = useState(null);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [isCapturing, setIsCapturing] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [message, setMessage] = useState(null);
  
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  
  useEffect(() => {
    // Auto-select method if only one is required
    if (requiredFactors?.length === 1) {
      setSelectedMethod(requiredFactors[0]);
    }
    
    return () => {
      // Cleanup
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, [requiredFactors]);
  
  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 320, height: 240, facingMode: 'user' }
      });
      
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        streamRef.current = stream;
        setIsCapturing(true);
      }
    } catch (error) {
      errorTracker.captureError(error, 'BiometricAuth:CameraAccess', {}, 'error');
      setMessage({
        type: 'error',
        text: 'Failed to access camera'
      });
    }
  };
  
  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setIsCapturing(false);
  };
  
  const authenticateWithFace = async () => {
    if (!videoRef.current || !canvasRef.current) return;
    
    setIsAuthenticating(true);
    setMessage({ type: 'info', text: 'Analyzing face...' });
    
    try {
      // Capture frame
      const canvas = canvasRef.current;
      const video = videoRef.current;
      canvas.width = 160;
      canvas.height = 160;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, 160, 160);
      
      // Convert to blob
      const blob = await new Promise(resolve => {
        canvas.toBlob(resolve, 'image/jpeg', 0.95);
      });
      
      // Authenticate
      const result = await mfaService.authenticateWithBiometrics({ face: blob });
      
      if (result.success) {
        setMessage({ type: 'success', text: 'Face verified!' });
        stopCamera();
        setTimeout(() => onSuccess(result), 1000);
      } else {
        setMessage({ type: 'error', text: result.message || 'Face verification failed' });
      }
    } catch (error) {
      errorTracker.captureError(error, 'BiometricAuth:FaceAuthentication', {}, 'error');
      setMessage({ type: 'error', text: error.message || 'Authentication failed' });
    } finally {
      setIsAuthenticating(false);
    }
  };
  
  const authenticateWithVoice = async () => {
    setIsAuthenticating(true);
    setIsRecording(true);
    setMessage({ type: 'info', text: 'Recording... Say "My voice is my password"' });
    
    try {
      // Record voice
      const audioBlob = await mfaService.recordVoiceSample(3);
      setIsRecording(false);
      
      setMessage({ type: 'info', text: 'Verifying voice...' });
      
      // Authenticate
      const result = await mfaService.authenticateWithBiometrics({ voice: audioBlob });
      
      if (result.success) {
        setMessage({ type: 'success', text: 'Voice verified!' });
        setTimeout(() => onSuccess(result), 1000);
      } else {
        setMessage({ type: 'error', text: result.message || 'Voice verification failed' });
      }
    } catch (error) {
      errorTracker.captureError(error, 'BiometricAuth:VoiceAuthentication', {}, 'error');
      setMessage({ type: 'error', text: error.message || 'Authentication failed' });
      setIsRecording(false);
    } finally {
      setIsAuthenticating(false);
    }
  };
  
  const authenticateWithWebAuthn = async () => {
    setIsAuthenticating(true);
    setMessage({ type: 'info', text: 'Waiting for biometric authentication...' });
    
    try {
      // Use WebAuthn/Passkey for fingerprint
      const credential = await navigator.credentials.get({
        publicKey: {
          challenge: new Uint8Array(32),
          timeout: 60000,
          userVerification: 'required'
        }
      });
      
      if (credential) {
        setMessage({ type: 'success', text: 'Biometric verified!' });
        setTimeout(() => onSuccess({ success: true }), 1000);
      }
    } catch (error) {
      errorTracker.captureError(error, 'BiometricAuth:WebAuthn', {}, 'error');
      setMessage({ type: 'error', text: 'Biometric authentication failed' });
    } finally {
      setIsAuthenticating(false);
    }
  };
  
  const handleAuthenticate = async () => {
    switch (selectedMethod) {
      case 'face':
        if (!isCapturing) {
          await startCamera();
        } else {
          await authenticateWithFace();
        }
        break;
      case 'voice':
        await authenticateWithVoice();
        break;
      case 'fingerprint':
        await authenticateWithWebAuthn();
        break;
      default:
        setMessage({ type: 'error', text: 'Please select an authentication method' });
    }
  };
  
  const renderMethodContent = () => {
    if (selectedMethod === 'face' && isCapturing) {
      return (
        <>
          <VideoContainer>
            <Video ref={videoRef} autoPlay playsInline muted />
          </VideoContainer>
          <Canvas ref={canvasRef} />
        </>
      );
    }
    
    if (selectedMethod === 'voice' && isRecording) {
      return (
        <RecordingIndicator>
          <div className="pulse-dot" />
          <span>Recording... Speak now!</span>
        </RecordingIndicator>
      );
    }
    
    const icons = {
      face: <FaCamera size={48} />,
      voice: <FaMicrophone size={48} />,
      fingerprint: <FaFingerprint size={48} />
    };
    
    const labels = {
      face: 'Face Recognition',
      voice: 'Voice Recognition',
      fingerprint: 'Fingerprint/Passkey'
    };
    
    return selectedMethod && (
      <div style={{ padding: '2rem 0' }}>
        <div style={{ color: 'var(--primary)', marginBottom: '1rem' }}>
          {icons[selectedMethod]}
        </div>
        <p style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '0.5rem' }}>
          {labels[selectedMethod]}
        </p>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          {selectedMethod === 'face' && 'Position your face in the camera'}
          {selectedMethod === 'voice' && 'Say "My voice is my password"'}
          {selectedMethod === 'fingerprint' && 'Use your device\'s biometric sensor'}
        </p>
      </div>
    );
  };
  
  return (
    <Container>
      <AuthCard>
        <Title>Biometric Authentication Required</Title>
        
        {message && (
          <Message type={message.type}>
            {message.type === 'success' && <FaCheck />}
            {message.type === 'error' && <FaTimes />}
            {message.type === 'info' && <FaSpinner className="fa-spin" />}
            {message.text}
          </Message>
        )}
        
        <MethodSelector>
          <MethodButton
            active={selectedMethod === 'face'}
            onClick={() => setSelectedMethod('face')}
            disabled={isAuthenticating}
          >
            <FaCamera size={24} />
            <span>Face</span>
          </MethodButton>
          
          <MethodButton
            active={selectedMethod === 'voice'}
            onClick={() => setSelectedMethod('voice')}
            disabled={isAuthenticating}
          >
            <FaMicrophone size={24} />
            <span>Voice</span>
          </MethodButton>
          
          <MethodButton
            active={selectedMethod === 'fingerprint'}
            onClick={() => setSelectedMethod('fingerprint')}
            disabled={isAuthenticating}
          >
            <FaFingerprint size={24} />
            <span>Fingerprint</span>
          </MethodButton>
        </MethodSelector>
        
        {renderMethodContent()}
        
        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
          <Button
            onClick={handleAuthenticate}
            disabled={!selectedMethod || isAuthenticating}
            loading={isAuthenticating}
            variant="primary"
          >
            {isCapturing && selectedMethod === 'face' ? 'Verify Face' : 'Authenticate'}
          </Button>
          
          {onCancel && (
            <Button onClick={onCancel} variant="secondary" disabled={isAuthenticating}>
              Cancel
            </Button>
          )}
        </div>
      </AuthCard>
    </Container>
  );
};

export default BiometricAuth;

