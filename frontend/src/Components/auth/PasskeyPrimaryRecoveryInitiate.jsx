import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import { FaKey, FaShieldAlt, FaCheckCircle, FaExclamationTriangle, FaUsers } from 'react-icons/fa';
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

const Input = styled.input`
  width: 100%;
  padding: 14px 16px;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 0.3s;
  font-family: ${props => props.mono ? "'Courier New', monospace" : 'inherit'};
  letter-spacing: ${props => props.mono ? '2px' : 'normal'};

  &:focus {
    outline: none;
    border-color: #667eea;
  }

  &::placeholder {
    color: #999;
    letter-spacing: normal;
  }
`;

const FormGroup = styled.div`
  margin-bottom: 20px;
`;

const Label = styled.label`
  display: block;
  margin-bottom: 8px;
  font-weight: 600;
  color: #333;
  font-size: 14px;
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

const Alert = styled.div`
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 20px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  background: ${props => {
    if (props.type === 'error') return '#fee';
    if (props.type === 'success') return '#efe';
    if (props.type === 'warning') return '#fff3cd';
    return '#e3f2fd';
  }};
  border-left: 4px solid ${props => {
    if (props.type === 'error') return '#c33';
    if (props.type === 'success') return '#2a7f2a';
    if (props.type === 'warning') return '#ffc107';
    return '#2196f3';
  }};
  color: ${props => {
    if (props.type === 'error') return '#c33';
    if (props.type === 'success') return '#2a7f2a';
    if (props.type === 'warning') return '#856404';
    return '#1976d2';
  }};

  svg {
    font-size: 20px;
    flex-shrink: 0;
    margin-top: 2px;
  }
`;

const FallbackOption = styled.div`
  background: #f8f9fa;
  border: 2px dashed #667eea;
  border-radius: 12px;
  padding: 20px;
  margin-top: 24px;
  text-align: center;

  h3 {
    margin: 0 0 12px 0;
    color: #667eea;
    font-size: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }

  p {
    margin: 0 0 16px 0;
    color: #666;
    font-size: 14px;
    line-height: 1.6;
  }
`;

const SuccessContainer = styled.div`
  text-align: center;
  padding: 40px 20px;

  svg {
    font-size: 64px;
    color: #2a7f2a;
    margin-bottom: 20px;
  }

  h2 {
    color: #333;
    margin-bottom: 16px;
  }

  p {
    color: #666;
    margin-bottom: 24px;
    line-height: 1.6;
  }
`;

const PasskeyPrimaryRecoveryInitiate = () => {
  const [step, setStep] = useState(1); // 1: identify, 2: enter key, 3: success
  const [username, setUsername] = useState('');
  const [recoveryKey, setRecoveryKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [recoveryAttemptId, setRecoveryAttemptId] = useState(null);
  const [userId, setUserId] = useState(null);
  const [hasBackups, setHasBackups] = useState(false);
  const [backupCount, setBackupCount] = useState(0);
  const [recoveredCredential, setRecoveredCredential] = useState(null);
  const [fallbackAvailable, setFallbackAvailable] = useState(false);
  const navigate = useNavigate();

  const handleIdentifyUser = async (e) => {
    e.preventDefault();
    if (!username) {
      setError('Please enter your email or username');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await ApiService.passkeyPrimaryRecovery.initiateRecovery({
        username_or_email: username
      });

      setUserId(response.data.user_id);
      setHasBackups(response.data.has_backups);
      setBackupCount(response.data.backup_count);
      setRecoveryAttemptId(response.data.recovery_attempt_id);
      setFallbackAvailable(response.data.fallback_available || false);

      if (response.data.has_backups) {
        setStep(2);
        toast.success('Account found! Please enter your recovery key.');
      } else {
        toast.error('No recovery backups found for this account');
        setError('No active recovery backups found. You may need to use guardian-based recovery.');
      }
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'Failed to identify account. Please try again.';
      setError(errorMsg);
      toast.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleCompleteRecovery = async (e) => {
    e.preventDefault();
    if (!recoveryKey) {
      setError('Please enter your recovery key');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await ApiService.passkeyPrimaryRecovery.completeRecovery({
        recovery_attempt_id: recoveryAttemptId,
        recovery_key: recoveryKey.replace(/-/g, ''), // Remove hyphens
        user_id: userId
      });

      setRecoveredCredential(response.data.passkey_credential);
      setStep(3);
      toast.success('Passkey recovered successfully!');
    } catch (err) {
      const errorData = err.response?.data;
      const errorMsg = errorData?.error || 'Recovery failed. Please try again.';
      setError(errorMsg);
      setFallbackAvailable(errorData?.fallback_available || false);
      toast.error(errorMsg);

      if (errorData?.fallback_available) {
        // Show fallback option
        setError(errorData.message || errorMsg);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleFallbackToSocialMesh = async () => {
    if (!userId || !recoveryAttemptId) {
      toast.error('Cannot initiate fallback recovery');
      return;
    }

    setLoading(true);

    try {
      const response = await ApiService.passkeyPrimaryRecovery.fallbackToSocialMesh({
        primary_recovery_attempt_id: recoveryAttemptId,
        user_id: userId
      });

      toast.success('Fallback to social mesh recovery initiated!');
      navigate('/recovery/social-mesh', { 
        state: { 
          userId,
          primaryAttemptId: recoveryAttemptId,
          instructions: response.data.instructions
        }
      });
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'Failed to initiate fallback recovery.';
      toast.error(errorMsg);
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  // Render step 1: Identify user
  if (step === 1) {
    return (
      <Container>
        <Card>
          <Header>
            <h1>
              <FaKey /> Recover Your Passkey
            </h1>
            <p>Primary recovery using your recovery key</p>
          </Header>
          <Content>
            <p style={{ marginBottom: '24px', lineHeight: '1.6', color: '#666' }}>
              Enter your account email or username to begin the recovery process.
              You'll need your 24-character recovery key to complete recovery.
            </p>

            {error && (
              <Alert type="error">
                <FaExclamationTriangle />
                <span>{error}</span>
              </Alert>
            )}

            <form onSubmit={handleIdentifyUser}>
              <FormGroup>
                <Label htmlFor="username">Email or Username</Label>
                <Input
                  type="text"
                  id="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="name@gmail.com or username"
                  required
                  autoFocus
                />
              </FormGroup>

              <Button type="submit" disabled={loading}>
                {loading ? 'Checking Account...' : 'Continue'}
              </Button>
            </form>

            <FallbackOption>
              <h3>
                <FaUsers /> Don't Have Your Recovery Key?
              </h3>
              <p>
                If you don't have your recovery key, you can use guardian-based recovery.
                This process takes 3-7 days and requires help from your trusted guardians.
              </p>
              <Button secondary onClick={() => navigate('/recovery/social-mesh')}>
                Use Guardian-Based Recovery
              </Button>
            </FallbackOption>

            <Button secondary onClick={() => navigate('/')} style={{ marginTop: '12px' }}>
              Back to Login
            </Button>
          </Content>
        </Card>
      </Container>
    );
  }

  // Render step 2: Enter recovery key
  if (step === 2) {
    return (
      <Container>
        <Card>
          <Header>
            <h1>
              <FaKey /> Enter Recovery Key
            </h1>
            <p>Decrypt your passkey backup</p>
          </Header>
          <Content>
            <Alert type="success">
              <FaCheckCircle />
              <div>
                <strong>Account Found!</strong>
                <p style={{ margin: '4px 0 0 0' }}>
                  We found {backupCount} active backup{backupCount !== 1 ? 's' : ''} for your account.
                  Enter your recovery key to decrypt your passkey.
                </p>
              </div>
            </Alert>

            {error && (
              <Alert type="error">
                <FaExclamationTriangle />
                <span>{error}</span>
              </Alert>
            )}

            <form onSubmit={handleCompleteRecovery}>
              <FormGroup>
                <Label htmlFor="recovery-key">Recovery Key (24 characters)</Label>
                <Input
                  type="text"
                  id="recovery-key"
                  value={recoveryKey}
                  onChange={(e) => setRecoveryKey(e.target.value.toUpperCase())}
                  placeholder="XXXX-XXXX-XXXX-XXXX-XXXX-XXXX"
                  required
                  autoFocus
                  mono
                  maxLength={29} // 24 chars + 5 hyphens
                />
                <small style={{ color: '#666', fontSize: '13px' }}>
                  Enter with or without hyphens
                </small>
              </FormGroup>

              <Button type="submit" disabled={loading}>
                {loading ? 'Decrypting...' : 'Recover Passkey'}
              </Button>
            </form>

            {fallbackAvailable && (
              <FallbackOption>
                <h3>
                  <FaUsers /> Recovery Key Not Working?
                </h3>
                <p>
                  If you don't have the correct recovery key, you can fall back to guardian-based recovery.
                  Your trusted guardians will help verify your identity.
                </p>
                <Button secondary onClick={handleFallbackToSocialMesh} disabled={loading}>
                  Use Guardian-Based Recovery
                </Button>
              </FallbackOption>
            )}

            <Button secondary onClick={() => setStep(1)} style={{ marginTop: '12px' }}>
              Go Back
            </Button>
          </Content>
        </Card>
      </Container>
    );
  }

  // Render step 3: Success
  if (step === 3) {
    return (
      <Container>
        <Card>
          <Header>
            <h1>
              <FaCheckCircle /> Recovery Complete!
            </h1>
            <p>Your passkey has been restored</p>
          </Header>
          <Content>
            <SuccessContainer>
              <FaShieldAlt style={{ color: '#2a7f2a' }} />
              <h2>Passkey Successfully Recovered!</h2>
              <p>
                Your passkey has been decrypted and restored. You can now use it to log in to your account.
              </p>
              {recoveredCredential && (
                <div style={{ background: '#f8f9fa', padding: '16px', borderRadius: '8px', marginBottom: '20px', textAlign: 'left' }}>
                  <h4 style={{ margin: '0 0 12px 0' }}>Recovered Passkey Details:</h4>
                  <p style={{ margin: '4px 0', fontSize: '14px' }}>
                    <strong>Device:</strong> {recoveredCredential.device_type || 'Unknown'}
                  </p>
                  <p style={{ margin: '4px 0', fontSize: '14px' }}>
                    <strong>Created:</strong> {new Date(recoveredCredential.created_at).toLocaleDateString()}
                  </p>
                  <p style={{ margin: '4px 0', fontSize: '14px' }}>
                    <strong>RP ID:</strong> {recoveredCredential.rp_id}
                  </p>
                </div>
              )}
            </SuccessContainer>

            <Alert type="warning">
              <FaExclamationTriangle />
              <div>
                <strong>Next Steps:</strong>
                <ul style={{ margin: '8px 0 0 0', paddingLeft: '20px' }}>
                  <li>Log in with your recovered passkey</li>
                  <li>Consider creating a new recovery backup</li>
                  <li>Set up guardian-based recovery as a backup</li>
                  <li>Review your security settings</li>
                </ul>
              </div>
            </Alert>

            <Button onClick={() => navigate('/')}>
              Go to Login
            </Button>
          </Content>
        </Card>
      </Container>
    );
  }

  return null;
};

export default PasskeyPrimaryRecoveryInitiate;

