import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import { FaKey, FaShieldAlt, FaCheckCircle, FaCopy, FaExclamationTriangle, FaDownload } from 'react-icons/fa';
import { QRCodeSVG } from 'qrcode.react';
import ApiService from '../../services/api';
import toast from 'react-hot-toast';

const Container = styled.div`
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
`;

const Card = styled.div`
  background: white;
  border-radius: 16px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
  max-width: 600px;
  width: 100%;
  overflow: hidden;
`;

const Header = styled.div`
  padding: 32px;
  text-align: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;

  h1 {
    font-size: 28px;
    margin: 0 0 8px 0;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
  }

  p {
    margin: 0;
    opacity: 0.9;
    font-size: 14px;
  }
`;

const Content = styled.div`
  padding: 32px;
`;

const RecoveryKeyDisplay = styled.div`
  background: #f8f9fa;
  border: 2px dashed #667eea;
  border-radius: 12px;
  padding: 24px;
  margin: 24px 0;
  text-align: center;
`;

const RecoveryKeyText = styled.div`
  font-family: 'Courier New', monospace;
  font-size: 24px;
  font-weight: bold;
  color: #667eea;
  letter-spacing: 2px;
  margin: 16px 0;
  user-select: all;
  word-break: break-all;
`;

const WarningBox = styled.div`
  background: #fff3cd;
  border: 2px solid #ffc107;
  border-radius: 8px;
  padding: 16px;
  margin: 20px 0;
  display: flex;
  align-items: flex-start;
  gap: 12px;

  svg {
    color: #ff9800;
    font-size: 24px;
    flex-shrink: 0;
    margin-top: 2px;
  }

  div {
    flex: 1;
  }

  h4 {
    margin: 0 0 8px 0;
    color: #ff9800;
    font-size: 16px;
  }

  p {
    margin: 0;
    color: #856404;
    font-size: 14px;
    line-height: 1.5;
  }
`;

const Button = styled.button`
  width: 100%;
  padding: 14px;
  background: ${props => props.secondary ? 'white' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'};
  color: ${props => props.secondary ? '#667eea' : 'white'};
  border: ${props => props.secondary ? '2px solid #667eea' : 'none'};
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: ${props => props.secondary ? '12px' : '0'};

  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

const CheckboxGroup = styled.div`
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin: 20px 0;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;

  input[type="checkbox"] {
    margin-top: 4px;
    width: 18px;
    height: 18px;
    cursor: pointer;
  }

  label {
    cursor: pointer;
    font-size: 14px;
    color: #333;
    line-height: 1.5;
  }
`;

const QRCodeContainer = styled.div`
  display: flex;
  justify-content: center;
  margin: 20px 0;
  padding: 20px;
  background: white;
  border-radius: 8px;
`;

const ButtonGroup = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 20px;
`;

const PasskeyPrimaryRecoverySetup = ({ passkeyCredentialId, deviceName, onComplete, onSkip }) => {
  const [step, setStep] = useState(1); // 1: intro, 2: display key, 3: confirm
  const [recoveryKey, setRecoveryKey] = useState('');
  const [backupId, setBackupId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [keyCopied, setKeyCopied] = useState(false);
  const [keyDownloaded, setKeyDownloaded] = useState(false);
  const [confirmSaved, setConfirmSaved] = useState(false);
  const navigate = useNavigate();

  const handleSetupRecovery = async () => {
    if (!passkeyCredentialId) {
      setError('No passkey credential ID provided');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await ApiService.passkeyPrimaryRecovery.setupRecovery({
        passkey_credential_id: passkeyCredentialId,
        device_name: deviceName || 'My Device'
      });

      setRecoveryKey(response.data.recovery_key);
      setBackupId(response.data.backup_id);
      setStep(2);
      toast.success('Recovery key generated successfully!');
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'Failed to set up recovery. Please try again.';
      setError(errorMsg);
      toast.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(recoveryKey);
    setKeyCopied(true);
    toast.success('Recovery key copied to clipboard!');
    setTimeout(() => setKeyCopied(false), 3000);
  };

  const downloadRecoveryKey = () => {
    const blob = new Blob([`SecureVault Passkey Recovery Key\n\nDevice: ${deviceName || 'My Device'}\nRecovery Key: ${recoveryKey}\n\nGenerated: ${new Date().toISOString()}\n\nIMPORTANT: Keep this key secure and private. Anyone with this key can recover your passkey.`], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `securevault-recovery-key-${new Date().getTime()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setKeyDownloaded(true);
    toast.success('Recovery key downloaded!');
  };

  const handleComplete = () => {
    if (!confirmSaved) {
      toast.error('Please confirm you have saved your recovery key');
      return;
    }

    toast.success('Passkey recovery setup complete!');
    if (onComplete) {
      onComplete({ backupId, deviceName });
    } else {
      navigate('/settings/passkeys');
    }
  };

  const handleSkip = () => {
    if (window.confirm('Are you sure you want to skip setting up recovery? You may not be able to recover your passkey if you lose access to this device.')) {
      if (onSkip) {
        onSkip();
      } else {
        navigate('/settings/passkeys');
      }
    }
  };

  // Render step 1: Introduction
  if (step === 1) {
    return (
      <Container>
        <Card>
          <Header>
            <h1>
              <FaShieldAlt /> Set Up Passkey Recovery
            </h1>
            <p>Protect your passkey with quantum-resistant encryption</p>
          </Header>
          <Content>
            <h3>Why Set Up Recovery?</h3>
            <p style={{ marginBottom: '16px', lineHeight: '1.6', color: '#666' }}>
              A recovery key allows you to regain access to your passkey if you lose your device or can't authenticate.
              This backup is encrypted with quantum-resistant Kyber + AES-GCM encryption.
            </p>

            <h3>What You'll Get:</h3>
            <ul style={{ marginBottom: '24px', lineHeight: '1.8', color: '#666' }}>
              <li>A 24-character recovery key (one-time display)</li>
              <li>Quantum-resistant encryption (Kyber + AES-GCM)</li>
              <li>Instant recovery (no waiting for guardians)</li>
              <li>Fallback to social mesh recovery if needed</li>
            </ul>

            <WarningBox>
              <FaExclamationTriangle />
              <div>
                <h4>Important Security Notice</h4>
                <p>
                  Your recovery key will be shown ONLY ONCE. Store it in a secure location such as a password manager or physical safe.
                  Without this key, you'll need to use guardian-based recovery (3-7 days).
                </p>
              </div>
            </WarningBox>

            {error && (
              <div style={{ padding: '12px', background: '#fee', color: '#c33', borderRadius: '8px', marginBottom: '16px' }}>
                {error}
              </div>
            )}

            <Button onClick={handleSetupRecovery} disabled={loading}>
              {loading ? 'Generating Recovery Key...' : <>
                <FaKey /> Generate Recovery Key
              </>}
            </Button>

            <Button secondary onClick={handleSkip}>
              Skip for Now
            </Button>

            <p style={{ marginTop: '16px', fontSize: '13px', color: '#999', textAlign: 'center' }}>
              You can also set up guardian-based recovery later for additional security.
            </p>
          </Content>
        </Card>
      </Container>
    );
  }

  // Render step 2: Display recovery key
  if (step === 2) {
    return (
      <Container>
        <Card>
          <Header>
            <h1>
              <FaKey /> Your Recovery Key
            </h1>
            <p>Save this key in a secure location</p>
          </Header>
          <Content>
            <WarningBox>
              <FaExclamationTriangle />
              <div>
                <h4>⚠️ Save This Key NOW</h4>
                <p>
                  This recovery key will be shown ONLY ONCE and cannot be retrieved later.
                  If you lose both your device and this key, you'll need guardian-based recovery.
                </p>
              </div>
            </WarningBox>

            <RecoveryKeyDisplay>
              <p style={{ margin: '0 0 8px 0', fontSize: '14px', color: '#666', fontWeight: '600' }}>
                Your Recovery Key:
              </p>
              <RecoveryKeyText>{recoveryKey}</RecoveryKeyText>
            </RecoveryKeyDisplay>

            <ButtonGroup>
              <Button secondary onClick={copyToClipboard}>
                <FaCopy /> {keyCopied ? 'Copied!' : 'Copy Key'}
              </Button>
              <Button secondary onClick={downloadRecoveryKey}>
                <FaDownload /> {keyDownloaded ? 'Downloaded!' : 'Download Key'}
              </Button>
            </ButtonGroup>

            <QRCodeContainer>
              <QRCodeSVG value={recoveryKey} size={200} level="H" />
            </QRCodeContainer>
            <p style={{ textAlign: 'center', fontSize: '13px', color: '#999', marginTop: '-8px' }}>
              Scan this QR code to save the key on another device
            </p>

            <h4 style={{ marginTop: '24px', marginBottom: '12px' }}>Where to Store Your Recovery Key:</h4>
            <ul style={{ marginBottom: '20px', lineHeight: '1.8', color: '#666', fontSize: '14px' }}>
              <li>In a password manager (recommended)</li>
              <li>In a physical safe or secure location</li>
              <li>With a trusted family member (printed and sealed)</li>
              <li>In a bank safe deposit box</li>
            </ul>

            <p style={{ fontSize: '13px', color: '#ff5722', fontWeight: '600', marginBottom: '16px' }}>
              ❌ DO NOT store in: email, cloud notes, unencrypted files, or photos
            </p>

            <CheckboxGroup>
              <input
                type="checkbox"
                id="confirm-saved"
                checked={confirmSaved}
                onChange={(e) => setConfirmSaved(e.target.checked)}
              />
              <label htmlFor="confirm-saved">
                I have securely saved my recovery key and understand it cannot be shown again
              </label>
            </CheckboxGroup>

            <Button onClick={() => setStep(3)} disabled={!confirmSaved}>
              <FaCheckCircle /> Continue
            </Button>
          </Content>
        </Card>
      </Container>
    );
  }

  // Render step 3: Final confirmation
  if (step === 3) {
    return (
      <Container>
        <Card>
          <Header>
            <h1>
              <FaCheckCircle /> Setup Complete!
            </h1>
            <p>Your passkey is now protected</p>
          </Header>
          <Content>
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <FaShieldAlt style={{ fontSize: '64px', color: '#4caf50', marginBottom: '20px' }} />
              <h2 style={{ margin: '0 0 16px 0', color: '#333' }}>Passkey Recovery Activated</h2>
              <p style={{ color: '#666', lineHeight: '1.6', marginBottom: '24px' }}>
                Your passkey backup has been encrypted with quantum-resistant encryption and stored securely.
                You can now recover your passkey using your recovery key if needed.
              </p>
            </div>

            <div style={{ background: '#f8f9fa', padding: '20px', borderRadius: '8px', marginBottom: '20px' }}>
              <h3 style={{ margin: '0 0 12px 0', fontSize: '16px' }}>What's Next?</h3>
              <ul style={{ margin: 0, paddingLeft: '20px', lineHeight: '1.8', color: '#666' }}>
                <li>Your recovery key is ready to use immediately</li>
                <li>Consider setting up guardian-based recovery as a backup</li>
                <li>Test your passkey on this device to ensure it works</li>
                <li>You can manage your recovery options in Settings</li>
              </ul>
            </div>

            <Button onClick={handleComplete}>
              Go to Passkey Management
            </Button>

            <p style={{ marginTop: '16px', fontSize: '13px', color: '#999', textAlign: 'center' }}>
              Backup ID: {backupId} | Device: {deviceName || 'My Device'}
            </p>
          </Content>
        </Card>
      </Container>
    );
  }

  return null;
};

export default PasskeyPrimaryRecoverySetup;

