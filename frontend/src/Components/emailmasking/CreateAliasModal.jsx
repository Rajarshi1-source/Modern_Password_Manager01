import React, { useState } from 'react';
import styled from 'styled-components';
import { FaTimes, FaRandom } from 'react-icons/fa';

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
  max-width: 600px;
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

const FormGroup = styled.div`
  margin-bottom: 1.5rem;

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
`;

const Input = styled.input`
  width: 100%;
  padding: 0.875rem;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 1rem;
  transition: all 0.2s ease;

  &:focus {
    outline: none;
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
  }

  &:disabled {
    background: #f5f5f5;
    cursor: not-allowed;
  }
`;

const TextArea = styled.textarea`
  width: 100%;
  padding: 0.875rem;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 1rem;
  min-height: 100px;
  resize: vertical;
  transition: all 0.2s ease;

  &:focus {
    outline: none;
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
  }
`;

const Select = styled.select`
  width: 100%;
  padding: 0.875rem;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 1rem;
  background: white;
  cursor: pointer;
  transition: all 0.2s ease;

  &:focus {
    outline: none;
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
  }
`;

const ProviderInfo = styled.div`
  background: #f0f4ff;
  border: 2px solid #667eea;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1.5rem;

  .quota-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.875rem;
    color: #333;

    .label {
      font-weight: 600;
    }

    .value {
      color: #667eea;
      font-weight: 700;
    }
  }

  .warning {
    margin-top: 0.5rem;
    color: #ff5722;
    font-size: 0.875rem;
    font-weight: 600;
  }
`;

const VaultItemLink = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;

  .link-btn {
    padding: 0.5rem 1rem;
    background: #667eea;
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 600;
    transition: all 0.2s ease;

    &:hover {
      background: #4A6CF7;
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
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
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

const CreateAliasModal = ({ providers, onClose, onSubmit }) => {
  const defaultProvider = providers.find(p => p.is_default) || providers[0];
  
  const [formData, setFormData] = useState({
    provider: defaultProvider?.provider || 'simplelogin',
    name: '',
    description: '',
    vault_item_id: ''
  });

  const [loading, setLoading] = useState(false);

  const selectedProvider = providers.find(p => p.provider === formData.provider);
  const canCreate = selectedProvider?.monthly_quota === 0 || 
                    (selectedProvider?.aliases_created_this_month < selectedProvider?.monthly_quota);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!canCreate) {
      return;
    }

    setLoading(true);
    try {
      await onSubmit(formData);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal onClick={onClose}>
      <ModalContent onClick={(e) => e.stopPropagation()}>
        <Header>
          <h2>Create New Email Alias</h2>
          <button className="close-btn" onClick={onClose}>
            <FaTimes />
          </button>
        </Header>

        <form onSubmit={handleSubmit}>
          <FormGroup>
            <label>Provider</label>
            <Select
              value={formData.provider}
              onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
              required
            >
              {providers.map(provider => (
                <option key={provider.provider} value={provider.provider}>
                  {provider.provider === 'simplelogin' ? 'SimpleLogin' : 
                   provider.provider === 'anonaddy' ? 'AnonAddy' : 
                   provider.provider}
                </option>
              ))}
            </Select>
          </FormGroup>

          {selectedProvider && (
            <ProviderInfo>
              <div className="quota-info">
                <span className="label">Monthly Quota:</span>
                <span className="value">
                  {selectedProvider.monthly_quota === 0 
                    ? 'Unlimited' 
                    : `${selectedProvider.aliases_created_this_month} / ${selectedProvider.monthly_quota}`}
                </span>
              </div>
              {!canCreate && (
                <div className="warning">
                  ⚠️ You have reached your monthly quota for this provider
                </div>
              )}
            </ProviderInfo>
          )}

          <FormGroup>
            <label>Alias Name (Optional)</label>
            <Input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g., Shopping Account, Newsletter Signup"
            />
            <div className="helper-text">
              A friendly name to help you remember what this alias is for
            </div>
          </FormGroup>

          <FormGroup>
            <label>Description (Optional)</label>
            <TextArea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="What will you use this alias for?"
            />
          </FormGroup>

          <FormGroup>
            <label>Link to Vault Item (Optional)</label>
            <Input
              type="text"
              value={formData.vault_item_id}
              onChange={(e) => setFormData({ ...formData, vault_item_id: e.target.value })}
              placeholder="Enter vault item ID"
            />
            <div className="helper-text">
              Associate this alias with a password vault item
            </div>
          </FormGroup>

          <Actions>
            <Button type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button 
              type="submit" 
              variant="primary"
              disabled={loading || !canCreate}
            >
              {loading ? 'Creating...' : 'Create Alias'}
            </Button>
          </Actions>
        </form>
      </ModalContent>
    </Modal>
  );
};

export default CreateAliasModal;
