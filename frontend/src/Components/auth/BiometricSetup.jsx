import React, { useState, useRef, useEffect } from 'react';
import styled from 'styled-components';
import { FaCamera, FaMicrophone, FaCheck, FaTimes, FaSpinner } from 'react-icons/fa';
import mfaService from '../../services/mfaService';
import { errorTracker } from '../../services/errorTracker';
import Button from '../common/Button';

const Container = styled.div`
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
`;

const Title = styled.h2`
  text-align: center;
  margin-bottom: 2rem;
  color: var(--text-primary);
`;

const TabContainer = styled.div`
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;
  border-bottom: 2px solid var(--border-color);
`;

const Tab = styled.button`
  flex: 1;
  padding: 1rem;
  background: ${props => props.active ? 'var(--primary)' : 'transparent'};
  color: ${props => props.active ? 'white' : 'var(--text-secondary)'};
  border: none;
  border-bottom: 3px solid ${props => props.active ? 'var(--primary)' : 'transparent'};
  cursor: pointer;
  font-weight: 600;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  
  &:hover {
    background: ${props => props.active ? 'var(--primary-dark)' : 'var(--primary-light)'};
  }
`;

const SetupCard = styled.div`
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 2rem;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
`;

const VideoContainer = styled.div`
  position: relative;
  width: 100%;
  max-width: 640px;
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

const RecordingIndicator = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 1rem;
  background: ${props => props.recording ? 'var(--danger)' : 'var(--bg-primary)'};
  color: ${props => props.recording ? 'white' : 'var(--text-primary)'};
  border-radius: 8px;
  margin-bottom: 1rem;
`;

const RecordingDot = styled.div`
  width: 12px;
  height: 12px;
  background: white;
  border-radius: 50%;
  animation: pulse 1s infinite;
  
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
`;

const Instructions = styled.div`
  background: var(--primary-light);
  border-left: 4px solid var(--primary);
  padding: 1rem;
  margin-bottom: 1.5rem;
  border-radius: 4px;
`;

const ButtonGroup = styled.div`
  display: flex;
  gap: 1rem;
  justify-content: center;
  margin-top: 1.5rem;
`;

const Message = styled.div`
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  
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

const BiometricSetup = ({ onComplete }) => {
  const [activeTab, setActiveTab] = useState('face');
  const [isCapturing, setIsCapturing] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [message, setMessage] = useState(null);
  const [loading, setLoading] = useState(false);
  
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  
  useEffect(() => {
    return () => {
      // Cleanup: stop any active streams
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, []);
  
  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: 640,
          height: 480,
          facingMode: 'user'
        }
      });
      
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        streamRef.current = stream;
        setIsCapturing(true);
      }
    } catch (error) {
      errorTracker.captureError(error, 'BiometricSetup:CameraAccess', {}, 'error');
      setMessage({
        type: 'error',
        text: 'Failed to access camera. Please grant camera permissions.'
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
  
  const captureFaceImage = async () => {
    if (!videoRef.current || !canvasRef.current) return;
    
    setLoading(true);
    setMessage({ type: 'info', text: 'Capturing face...' });
    
    // Countdown before capture
    for (let i = 3; i > 0; i--) {
      setCountdown(i);
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    setCountdown(0);
    
    try {
      // Capture frame from video
      const canvas = canvasRef.current;
      const video = videoRef.current;
      
      canvas.width = 160;
      canvas.height = 160;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, 160, 160);
      
      // Convert canvas to blob
      const blob = await new Promise(resolve => {
        canvas.toBlob(resolve, 'image/jpeg', 0.95);
      });
      
      // Register face with backend
      const result = await mfaService.registerFace(blob);
      
      if (result.success) {
        setMessage({
          type: 'success',
          text: `Face registered successfully! Liveness score: ${(result.liveness_score * 100).toFixed(1)}%`
        });
        stopCamera();
        
        setTimeout(() => {
          if (onComplete) onComplete('face');
        }, 2000);
      } else {
        setMessage({
          type: 'error',
          text: result.message || 'Face registration failed'
        });
      }
    } catch (error) {
      errorTracker.captureError(error, 'BiometricSetup:FaceCapture', {}, 'error');
      setMessage({
        type: 'error',
        text: error.message || 'Failed to register face'
      });
    } finally {
      setLoading(false);
    }
  };
  
  const startVoiceRecording = async () => {
    try {
      setMessage({ type: 'info', text: 'Recording voice... Please say "My voice is my password"' });
      setIsRecording(true);
      setLoading(true);
      
      // Record voice sample
      const audioBlob = await mfaService.recordVoiceSample(3);
      
      // Register voice with backend
      const result = await mfaService.registerVoice(audioBlob);
      
      setIsRecording(false);
      
      if (result.success) {
        setMessage({
          type: 'success',
          text: 'Voice registered successfully!'
        });
        
        setTimeout(() => {
          if (onComplete) onComplete('voice');
        }, 2000);
      } else {
        setMessage({
          type: 'error',
          text: result.message || 'Voice registration failed'
        });
      }
    } catch (error) {
      errorTracker.captureError(error, 'BiometricSetup:VoiceRecording', {}, 'error');
      setMessage({
        type: 'error',
        text: error.message || 'Failed to register voice'
      });
      setIsRecording(false);
    } finally {
      setLoading(false);
    }
  };
  
  const renderFaceSetup = () => (
    <>
      <Instructions>
        <strong>Face Recognition Setup:</strong>
        <ul style={{ marginTop: '0.5rem', marginBottom: 0, paddingLeft: '1.5rem' }}>
          <li>Position your face in the center of the camera</li>
          <li>Ensure good lighting</li>
          <li>Look directly at the camera</li>
          <li>Remove glasses or face coverings</li>
        </ul>
      </Instructions>
      
      <VideoContainer>
        <Video ref={videoRef} autoPlay playsInline muted />
        {countdown > 0 && (
          <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            fontSize: '4rem',
            color: 'white',
            fontWeight: 'bold',
            textShadow: '0 0 10px rgba(0,0,0,0.5)'
          }}>
            {countdown}
          </div>
        )}
      </VideoContainer>
      
      <Canvas ref={canvasRef} />
      
      <ButtonGroup>
        {!isCapturing ? (
          <Button onClick={startCamera} icon={<FaCamera />}>
            Start Camera
          </Button>
        ) : (
          <>
            <Button 
              onClick={captureFaceImage} 
              disabled={loading}
              loading={loading}
              variant="primary"
            >
              Capture Face
            </Button>
            <Button onClick={stopCamera} variant="secondary">
              Cancel
            </Button>
          </>
        )}
      </ButtonGroup>
    </>
  );
  
  const renderVoiceSetup = () => (
    <>
      <Instructions>
        <strong>Voice Recognition Setup:</strong>
        <ul style={{ marginTop: '0.5rem', marginBottom: 0, paddingLeft: '1.5rem' }}>
          <li>Find a quiet location</li>
          <li>Speak clearly and naturally</li>
          <li>Say: "My voice is my password"</li>
          <li>Recording will last 3 seconds</li>
        </ul>
      </Instructions>
      
      {isRecording && (
        <RecordingIndicator recording={isRecording}>
          <RecordingDot />
          <span>Recording... Speak now!</span>
        </RecordingIndicator>
      )}
      
      <div style={{ 
        textAlign: 'center', 
        padding: '3rem',
        background: 'var(--bg-primary)',
        borderRadius: '8px',
        marginBottom: '1.5rem'
      }}>
        <FaMicrophone size={64} color="var(--primary)" />
        <p style={{ marginTop: '1rem', fontSize: '1.2rem', fontWeight: '600' }}>
          Ready to record your voice?
        </p>
      </div>
      
      <ButtonGroup>
        <Button 
          onClick={startVoiceRecording}
          disabled={loading || isRecording}
          loading={loading}
          icon={<FaMicrophone />}
          variant="primary"
        >
          {isRecording ? 'Recording...' : 'Start Recording'}
        </Button>
      </ButtonGroup>
    </>
  );
  
  return (
    <Container>
      <Title>Biometric Authentication Setup</Title>
      
      {message && (
        <Message type={message.type}>
          {message.type === 'success' && <FaCheck />}
          {message.type === 'error' && <FaTimes />}
          {message.type === 'info' && <FaSpinner className="fa-spin" />}
          {message.text}
        </Message>
      )}
      
      <TabContainer>
        <Tab 
          active={activeTab === 'face'} 
          onClick={() => {
            setActiveTab('face');
            setMessage(null);
            stopCamera();
          }}
        >
          <FaCamera /> Face Recognition
        </Tab>
        <Tab 
          active={activeTab === 'voice'} 
          onClick={() => {
            setActiveTab('voice');
            setMessage(null);
            stopCamera();
          }}
        >
          <FaMicrophone /> Voice Recognition
        </Tab>
      </TabContainer>
      
      <SetupCard>
        {activeTab === 'face' && renderFaceSetup()}
        {activeTab === 'voice' && renderVoiceSetup()}
      </SetupCard>
    </Container>
  );
};

export default BiometricSetup;

