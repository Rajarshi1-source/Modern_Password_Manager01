import React, { useState } from 'react';
import styled from 'styled-components';
import axios from 'axios';
import { X, Key, Check, ExternalLink } from 'lucide-react';

const Overlay = styled.div`
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
  padding: 1rem;
`;

const Modal = styled.div`
  background: white;
  border-radius: 16px;
  max-width: 700px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
`;

const Header = styled.div`
  padding: 2rem;
  border-bottom: 1px solid var(--border, #e0e0e0);
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const Title = styled.h2`
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary, #1a1a1a);
  margin: 0;
`;

const CloseButton = styled.button`
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary, #666);
  padding: 0.5rem;
  
  &:hover {
    color: var(--text-primary, #1a1a1a);
  }
`;

const Body = styled.div`
  padding: 2rem;
`;

const ProviderList = styled.div`
  margin-bottom: 2rem;
`;

const ProviderCard = styled.div`
  background: var(--secondary, #f5f5f5);
  padding: 1.5rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const ProviderInfo = styled.div`
  flex: 1;
`;

const ProviderName = styled.div`
  font-weight: 600;
  font-size: 1.125rem;
  color: var(--text-primary, #1a1a1a);
  margin-bottom: 0.5rem;
`;

const ProviderMeta = styled.div`
  font-size: 0.875rem;
  color: var(--text-secondary, #666);
  display: flex;
  gap: 1rem;
`;

const StatusBadge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  background: ${props => props.active ? '#d4edda' : '#f8d7da'};
  color: ${props => props.active ? '#155724' : '#721c24'};
`;

const Divider = styled.div`
  height: 1px;
  background: var(--border, #e0e0e0);
  margin: 2rem 0;
`;

const SectionTitle = styled.h3`
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
  margin-bottom: 1rem;
`;

const FormGroup = styled.div`
  margin-bottom: 1.5rem;
`;

const Label = styled.label`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500;
  color: var(--text-primary, #1a1a1a);
  margin-bottom: 0.5rem;
`;

const Input = styled.input`
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--border, #e0e0e0);
  border-radius: 8px;
  font-size: 1rem;
  
  &:focus {
    outline: none;
    border-color: var(--primary, #4A6CF7);
  }
`;

const Select = styled.select`
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--border, #e0e0e0);
  border-radius: 8px;
  font-size: 1rem;
  cursor: pointer;
  
  &:focus {
    outline: none;
    border-color: var(--primary, #4A6CF7);
  }
`;

const Checkbox = styled.input`
  width: 18px;
  height: 18px;
  cursor: pointer;
`;

const CheckboxLabel = styled.label`
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.875rem;
  color: var(--text-primary, #1a1a1a);
  cursor: pointer;
`;

const HelpText = styled.div`
  font-size: 0.875rem;
  color: var(--text-secondary, #666);
  margin-top: 0.5rem;
`;

const InfoBox = styled.div`
  background: #e8f0fe;
  border-left: 4px solid var(--primary, #4A6CF7);
  padding: 1rem;
  border-radius: 4px;
  margin-bottom: 1.5rem;
  font-size: 0.875rem;
  
  a {
    color: var(--primary, #4A6CF7);
    text-decoration: none;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    
    &:hover {
      text-decoration: underline;
    }
  }
`;

const Footer = styled.div`
  padding: 1.5rem 2rem;
  border-top: 1px solid var(--border, #e0e0e0);
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
`;

const Button = styled.button`
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  
  ${props => props.primary ? `
    background: var(--primary, #4A6CF7);
    color: white;
    
    &:hover:not(:disabled) {
      background: var(--primary-dark, #3651d4);
    }
  ` : `
    background: var(--secondary, #f5f5f5);
    color: var(--text-primary, #1a1a1a);
    
    &:hover {
      background: var(--hover, #e5e5e5);
    }
  `}
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const ErrorMessage = styled.div`
  background: #f8d7da;
  color: #721c24;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1.5rem;
  font-size: 0.875rem;
`;

const SuccessMessage = styled.div`
  background: #d4edda;
  color: #155724;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1.5rem;
  font-size: 0.875rem;
`;

function ProviderSetupModal({ providers, onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    provider: 'simplelogin',
    api_key: '',
    is_default: providers.length === 0
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      await axios.post('/api/email-masking/providers/configure/', formData);
      setSuccess('Provider configured successfully!');
      setTimeout(() => {
        onSuccess();
      }, 1500);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to configure provider');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData({
      ...formData,
      [name]: type === 'checkbox' ? checked : value
    });
  };

  return (
    <Overlay onClick={onClose}>
      <Modal onClick={(e) => e.stopPropagation()}>
        <Header>
          <Title>Manage Email Masking Providers</Title>
          <CloseButton onClick={onClose}>
            <X size={24} />
          </CloseButton>
        </Header>

        <Body>
          {providers.length > 0 && (
            <>
              <SectionTitle>Configured Providers</SectionTitle>
              <ProviderList>
                {providers.map(p => (
                  <ProviderCard key={p.id}>
                    <ProviderInfo>
                      <ProviderName>{p.provider}</ProviderName>
                      <ProviderMeta>
                        <StatusBadge active={p.is_active}>
                          {p.is_active ? <><Check size={12} /> Active</> : 'Inactive'}
                        </StatusBadge>
                        {p.is_default && <span>⭐ Default</span>}
                        {p.monthly_quota > 0 && (
                          <span>Quota: {p.aliases_created_this_month}/{p.monthly_quota}</span>
                        )}
                        {p.last_sync_at && (
                          <span>Last sync: {new Date(p.last_sync_at).toLocaleDateString()}</span>
                        )}
                      </ProviderMeta>
                    </ProviderInfo>
                  </ProviderCard>
                ))}
              </ProviderList>
              <Divider />
            </>
          )}

          {error && <ErrorMessage>{error}</ErrorMessage>}
          {success && <SuccessMessage>{success}</SuccessMessage>}

          <SectionTitle>Add New Provider</SectionTitle>

          <InfoBox>
            Get your API key from:
            <br />
            • SimpleLogin: <a href="https://app.simplelogin.io/dashboard/api_key" target="_blank" rel="noopener noreferrer">
              Get API Key <ExternalLink size={14} />
            </a>
            <br />
            • AnonAddy: <a href="https://app.addy.io/settings/api" target="_blank" rel="noopener noreferrer">
              Get API Key <ExternalLink size={14} />
            </a>
          </InfoBox>

          <form onSubmit={handleSubmit}>
            <FormGroup>
              <Label>Provider</Label>
              <Select 
                name="provider"
                value={formData.provider}
                onChange={handleChange}
                required
              >
                <option value="simplelogin">SimpleLogin</option>
                <option value="anonaddy">AnonAddy</option>
              </Select>
            </FormGroup>

            <FormGroup>
              <Label>
                <Key size={18} />
                API Key
              </Label>
              <Input
                type="password"
                name="api_key"
                value={formData.api_key}
                onChange={handleChange}
                placeholder="Enter your API key"
                required
              />
              <HelpText>Your API key will be encrypted before storage</HelpText>
            </FormGroup>

            <FormGroup>
              <CheckboxLabel>
                <Checkbox
                  type="checkbox"
                  name="is_default"
                  checked={formData.is_default}
                  onChange={handleChange}
                />
                Set as default provider
              </CheckboxLabel>
            </FormGroup>
          </form>
        </Body>

        <Footer>
          <Button onClick={onClose}>Cancel</Button>
          <Button primary onClick={handleSubmit} disabled={loading || success}>
            {loading ? 'Configuring...' : 'Add Provider'}
          </Button>
        </Footer>
      </Modal>
    </Overlay>
  );
}

export default ProviderSetupModal;

