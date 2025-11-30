import React, { useState } from 'react';
import styled from 'styled-components';
import axios from 'axios';
import toast from 'react-hot-toast';
import { FaTimes, FaShieldAlt, FaCheckCircle, FaExternalLinkAlt } from 'react-icons/fa';

const Modal = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fadeIn 0.3s ease;

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
`;

const ModalContent = styled.div`
  background: white;
  border-radius: 16px;
  padding: 2rem;
  max-width: 700px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  animation: slideUp 0.3s ease;

  @keyframes slideUp {
    from {
      transform: translateY(50px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;

  h2 {
    font-size: 1.75rem;
    color: #333;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 1.5rem;
    color: #999;
    cursor: pointer;
    transition: all 0.2s ease;

    &:hover {
      color: #333;
      transform: rotate(90deg);
    }
  }
`;

const ProviderOptions = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
`;

const ProviderCard = styled.div`
  border: 2px solid ${props => props.selected ? '#667eea' : '#e0e0e0'};
  border-radius: 12px;
  padding: 1.5rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background: ${props => props.selected ? '#f0f4ff' : 'white'};

  &:hover {
    border-color: #667eea;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }

  .icon {
    font-size: 2.5rem;
    margin-bottom: 0.75rem;
    color: ${props => props.selected ? '#667eea' : '#999'};
  }

  .name {
    font-size: 1.1rem;
    font-weight: 600;
    color: #333;
    margin-bottom: 0.5rem;
  }

  .description {
    font-size: 0.875rem;
    color: #666;
  }
`;

const FormSection = styled.div`
  background: #f9f9f9;
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
`;

const FormGroup = styled.div`
  margin-bottom: 1.5rem;

  &:last-child {
    margin-bottom: 0;
  }

  label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 600;
    color: #333;
    font-size: 0.95rem;
  }

  .helper-text {
    font-size: 0.875rem;
    color: #666;
    margin-top: 0.25rem;
  }

  .link {
    color: #667eea;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    
    &:hover {
      text-decoration: underline;
    }
  }
`;

const Input = styled.input`
  width: 100%;
  padding: 0.875rem;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 1rem;
  font-family: 'Courier New', monospace;
  transition: all 0.2s ease;

  &:focus {
    outline: none;
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
  }
`;

const Checkbox = styled.label`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  user-select: none;

  input[type="checkbox"] {
    width: 18px;
    height: 18px;
    cursor: pointer;
  }

  span {
    font-size: 0.95rem;
    color: #333;
  }
`;

const Instructions = styled.div`
  background: #fff3cd;
  border: 2px solid #ffc107;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1.5rem;

  h4 {
    color: #333;
    margin-bottom: 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  ol {
    margin: 0;
    padding-left: 1.5rem;
    color: #666;

    li {
      margin-bottom: 0.5rem;
      line-height: 1.6;
    }
  }
`;

const Actions = styled.div`
  display: flex;
  gap: 1rem;
  margin-top: 2rem;
`;

const Button = styled.button`
  flex: 1;
  padding: 0.875rem 1.5rem;
  background: ${props => props.variant === 'primary' ? '#667eea' : '#e0e0e0'};
  color: ${props => props.variant === 'primary' ? 'white' : '#333'};
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 1rem;
  font-weight: 600;
  transition: all 0.3s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
  }
`;

const SuccessMessage = styled.div`
  background: #d4edda;
  border: 2px solid #28a745;
  border-radius: 8px;
  padding: 1rem;
  color: #155724;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;

  .icon {
    font-size: 1.5rem;
    color: #28a745;
  }
`;

const PROVIDERS = [
  {
    id: 'simplelogin',
    name: 'SimpleLogin',
    description: 'Open-source email alias service',
    apiKeyUrl: 'https://app.simplelogin.io/dashboard/api_key',
    docsUrl: 'https://github.com/simple-login/app/blob/master/docs/api.md'
  },
  {
    id: 'anonaddy',
    name: 'AnonAddy',
    description: 'Anonymous email forwarding',
    apiKeyUrl: 'https://app.addy.io/settings/api',
    docsUrl: 'https://app.addy.io/docs/'
  }
];

const ProviderSetup = ({ onClose, onSuccess }) => {
  const [selectedProvider, setSelectedProvider] = useState('simplelogin');
  const [apiKey, setApiKey] = useState('');
  const [setAsDefault, setSetAsDefault] = useState(true);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const provider = PROVIDERS.find(p => p.id === selectedProvider);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!apiKey.trim()) {
      toast.error('Please enter an API key');
      return;
    }

    setLoading(true);
    try {
      await axios.post('/api/email-masking/providers/configure/', {
        provider: selectedProvider,
        api_key: apiKey,
        is_default: setAsDefault
      });

      setSuccess(true);
      toast.success(`${provider.name} configured successfully!`);
      
      setTimeout(() => {
        onSuccess();
      }, 1500);
    } catch (error) {
      console.error('Error configuring provider:', error);
      toast.error(error.response?.data?.error || 'Failed to configure provider');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal onClick={onClose}>
      <ModalContent onClick={(e) => e.stopPropagation()}>
        <Header>
          <h2>
            <FaShieldAlt />
            Configure Email Masking Provider
          </h2>
          <button className="close-btn" onClick={onClose}>
            <FaTimes />
          </button>
        </Header>

        {success && (
          <SuccessMessage>
            <FaCheckCircle className="icon" />
            <div>
              <strong>Configuration Successful!</strong>
              <br />
              You can now create email aliases using {provider.name}.
            </div>
          </SuccessMessage>
        )}

        <form onSubmit={handleSubmit}>
          <ProviderOptions>
            {PROVIDERS.map(p => (
              <ProviderCard
                key={p.id}
                selected={selectedProvider === p.id}
                onClick={() => setSelectedProvider(p.id)}
              >
                <div className="icon">
                  <FaShieldAlt />
                </div>
                <div className="name">{p.name}</div>
                <div className="description">{p.description}</div>
              </ProviderCard>
            ))}
          </ProviderOptions>

          <Instructions>
            <h4>📋 How to get your API key:</h4>
            <ol>
              <li>
                Go to{' '}
                <a
                  href={provider.apiKeyUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="link"
                >
                  {provider.name} API settings
                  <FaExternalLinkAlt size={12} />
                </a>
              </li>
              <li>Sign in or create a free account</li>
              <li>Generate or copy your API key</li>
              <li>Paste it in the field below</li>
            </ol>
          </Instructions>

          <FormSection>
            <FormGroup>
              <label>API Key *</label>
              <Input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={`Enter your ${provider.name} API key`}
                required
                disabled={loading || success}
              />
              <div className="helper-text">
                Your API key is encrypted and stored securely. View{' '}
                <a
                  href={provider.docsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="link"
                >
                  API documentation
                  <FaExternalLinkAlt size={10} />
                </a>
              </div>
            </FormGroup>

            <FormGroup>
              <Checkbox>
                <input
                  type="checkbox"
                  checked={setAsDefault}
                  onChange={(e) => setSetAsDefault(e.target.checked)}
                  disabled={loading || success}
                />
                <span>Set as default provider for new aliases</span>
              </Checkbox>
            </FormGroup>
          </FormSection>

          <Actions>
            <Button type="button" onClick={onClose} disabled={loading}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={loading || success || !apiKey.trim()}
            >
              {loading ? 'Verifying...' : success ? 'Configured!' : 'Configure Provider'}
            </Button>
          </Actions>
        </form>
      </ModalContent>
    </Modal>
  );
};

export default ProviderSetup;

