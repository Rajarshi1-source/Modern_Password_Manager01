import React, { useState } from 'react';
import styled from 'styled-components';
import axios from 'axios';
import { X, Folder, Lock, Info, AlertCircle } from 'lucide-react';
import toast from 'react-hot-toast';

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
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
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
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 0;
`;

const CloseButton = styled.button`
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary, #666);
  padding: 0.5rem;
  border-radius: 8px;
  transition: all 0.2s ease;
  
  &:hover {
    background: var(--hover, #f5f5f5);
    color: var(--text-primary, #1a1a1a);
  }
`;

const Content = styled.div`
  padding: 2rem;
`;

const FormGroup = styled.div`
  margin-bottom: 1.5rem;
`;

const Label = styled.label`
  display: block;
  font-weight: 600;
  margin-bottom: 0.5rem;
  color: var(--text-primary, #1a1a1a);
  font-size: 0.875rem;
`;

const Input = styled.input`
  width: 100%;
  padding: 0.75rem 1rem;
  border: 2px solid var(--border, #e0e0e0);
  border-radius: 8px;
  font-size: 1rem;
  transition: all 0.2s ease;
  
  &:focus {
    outline: none;
    border-color: var(--primary, #4A6CF7);
    box-shadow: 0 0 0 3px rgba(74, 108, 247, 0.1);
  }
  
  &::placeholder {
    color: #999;
  }
`;

const TextArea = styled.textarea`
  width: 100%;
  padding: 0.75rem 1rem;
  border: 2px solid var(--border, #e0e0e0);
  border-radius: 8px;
  font-size: 1rem;
  min-height: 100px;
  resize: vertical;
  font-family: inherit;
  transition: all 0.2s ease;
  
  &:focus {
    outline: none;
    border-color: var(--primary, #4A6CF7);
    box-shadow: 0 0 0 3px rgba(74, 108, 247, 0.1);
  }
  
  &::placeholder {
    color: #999;
  }
`;

const CheckboxGroup = styled.div`
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  background: var(--background-secondary, #f9fafb);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    background: var(--hover, #f0f0f0);
  }
`;

const Checkbox = styled.input`
  width: 20px;
  height: 20px;
  cursor: pointer;
`;

const CheckboxLabel = styled.div`
  flex: 1;
  
  .title {
    font-weight: 600;
    color: var(--text-primary, #1a1a1a);
    margin-bottom: 0.25rem;
  }
  
  .description {
    font-size: 0.875rem;
    color: var(--text-secondary, #666);
  }
`;

const InfoBox = styled.div`
  display: flex;
  gap: 0.75rem;
  padding: 1rem;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 8px;
  margin-bottom: 1.5rem;
  
  svg {
    flex-shrink: 0;
    color: #0284c7;
  }
  
  .content {
    font-size: 0.875rem;
    color: #0c4a6e;
    line-height: 1.5;
  }
`;

const ErrorBox = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: #fef2f2;
  border: 1px solid #fca5a5;
  border-radius: 8px;
  margin-bottom: 1.5rem;
  color: #991b1b;
  font-size: 0.875rem;
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
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
  font-size: 1rem;
  
  ${props => props.primary ? `
    background: var(--primary, #4A6CF7);
    color: white;
    
    &:hover:not(:disabled) {
      background: var(--primary-dark, #3651d4);
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(74, 108, 247, 0.3);
    }
  ` : `
    background: transparent;
    color: var(--text-secondary, #666);
    
    &:hover:not(:disabled) {
      background: var(--hover, #f5f5f5);
      color: var(--text-primary, #1a1a1a);
    }
  `}
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

function CreateFolderModal({ onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    require_2fa: false
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.name.trim()) {
      setError('Folder name is required');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await axios.post('/api/vault/shared-folders/', formData);
      toast.success('Shared folder created successfully!');
      onSuccess();
    } catch (err) {
      console.error('Failed to create shared folder:', err);
      setError(err.response?.data?.error || 'Failed to create shared folder. Please try again.');
      toast.error('Failed to create shared folder');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Overlay onClick={(e) => e.target === e.currentTarget && onClose()}>
      <Modal>
        <form onSubmit={handleSubmit}>
          <Header>
            <Title>
              <Folder size={24} />
              Create Shared Folder
            </Title>
            <CloseButton type="button" onClick={onClose}>
              <X size={20} />
            </CloseButton>
          </Header>

          <Content>
            <InfoBox>
              <Info size={20} />
              <div className="content">
                <strong>Shared folders</strong> allow you to securely share passwords and credentials with team members using end-to-end encryption. You control who has access and what they can do.
              </div>
            </InfoBox>

            {error && (
              <ErrorBox>
                <AlertCircle size={18} />
                {error}
              </ErrorBox>
            )}

            <FormGroup>
              <Label htmlFor="name">Folder Name *</Label>
              <Input
                type="text"
                id="name"
                name="name"
                value={formData.name}
                onChange={handleChange}
                placeholder="e.g., Marketing Team, Dev Environment"
                required
                autoFocus
              />
            </FormGroup>

            <FormGroup>
              <Label htmlFor="description">Description (Optional)</Label>
              <TextArea
                id="description"
                name="description"
                value={formData.description}
                onChange={handleChange}
                placeholder="Add a description to help team members understand what this folder is for..."
              />
            </FormGroup>

            <FormGroup>
              <CheckboxGroup onClick={() => setFormData(prev => ({ ...prev, require_2fa: !prev.require_2fa }))}>
                <Checkbox
                  type="checkbox"
                  id="require_2fa"
                  name="require_2fa"
                  checked={formData.require_2fa}
                  onChange={handleChange}
                  onClick={(e) => e.stopPropagation()}
                />
                <CheckboxLabel>
                  <div className="title">
                    <Lock size={16} style={{ display: 'inline', marginRight: '0.5rem' }} />
                    Require 2FA for Access
                  </div>
                  <div className="description">
                    Members must verify their identity with two-factor authentication before accessing this folder
                  </div>
                </CheckboxLabel>
              </CheckboxGroup>
            </FormGroup>
          </Content>

          <Footer>
            <Button type="button" onClick={onClose} disabled={loading}>
              Cancel
            </Button>
            <Button type="submit" primary disabled={loading || !formData.name.trim()}>
              {loading ? 'Creating...' : 'Create Folder'}
            </Button>
          </Footer>
        </form>
      </Modal>
    </Overlay>
  );
}

export default CreateFolderModal;

