import React, { useState } from 'react';
import styled from 'styled-components';
import { FaEnvelope, FaToggleOn, FaToggleOff, FaTrash, FaEdit, FaChartLine, FaCopy, FaExternalLinkAlt } from 'react-icons/fa';
import toast from 'react-hot-toast';

const Card = styled.div`
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;

  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.15);
  }

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: ${props => props.active ? 'linear-gradient(90deg, #4caf50, #8bc34a)' : '#ccc'};
  }
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
`;

const AliasInfo = styled.div`
  flex: 1;

  .alias-email {
    font-size: 1.1rem;
    font-weight: 600;
    color: #333;
    margin-bottom: 0.25rem;
    word-break: break-all;
    display: flex;
    align-items: center;
    gap: 0.5rem;

    .copy-btn {
      background: none;
      border: none;
      color: #667eea;
      cursor: pointer;
      padding: 0.25rem;
      font-size: 0.9rem;
      transition: all 0.2s ease;

      &:hover {
        color: #4A6CF7;
        transform: scale(1.1);
      }
    }
  }

  .alias-name {
    font-size: 0.875rem;
    color: #666;
    margin-bottom: 0.5rem;
  }

  .provider-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    background: ${props => {
      if (props.provider === 'simplelogin') return '#667eea';
      if (props.provider === 'anonaddy') return '#4caf50';
      return '#999';
    }};
    color: white;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
  }
`;

const StatusBadge = styled.span`
  padding: 0.25rem 0.75rem;
  background: ${props => props.active ? '#4caf50' : '#ff9800'};
  color: white;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
`;

const Description = styled.p`
  font-size: 0.875rem;
  color: #666;
  margin: 1rem 0;
  line-height: 1.5;
  min-height: 2.5rem;
`;

const Stats = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
  margin: 1rem 0;
  padding: 0.75rem;
  background: #f5f5f5;
  border-radius: 8px;
`;

const StatItem = styled.div`
  text-align: center;

  .label {
    font-size: 0.7rem;
    color: #666;
    text-transform: uppercase;
    margin-bottom: 0.25rem;
  }

  .value {
    font-size: 1.25rem;
    font-weight: 700;
    color: ${props => props.color || '#333'};
  }
`;

const ForwardsTo = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: #666;
  margin-bottom: 1rem;
  padding: 0.5rem;
  background: #f9f9f9;
  border-radius: 6px;

  .icon {
    color: #667eea;
  }
`;

const Actions = styled.div`
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
`;

const ActionButton = styled.button`
  flex: 1;
  padding: 0.5rem 0.75rem;
  background: ${props => {
    if (props.variant === 'danger') return '#f44336';
    if (props.variant === 'primary') return '#667eea';
    if (props.variant === 'success') return '#4caf50';
    return '#e0e0e0';
  }};
  color: ${props => props.variant === 'default' ? '#333' : 'white'};
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  transition: all 0.2s ease;

  &:hover {
    opacity: 0.9;
    transform: translateY(-1px);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const EditModal = styled.div`
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
`;

const ModalContent = styled.div`
  background: white;
  border-radius: 12px;
  padding: 2rem;
  max-width: 500px;
  width: 90%;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);

  h3 {
    margin-bottom: 1.5rem;
    color: #333;
  }
`;

const FormGroup = styled.div`
  margin-bottom: 1.5rem;

  label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 600;
    color: #333;
  }

  input, textarea {
    width: 100%;
    padding: 0.75rem;
    border: 2px solid #e0e0e0;
    border-radius: 8px;
    font-size: 1rem;
    transition: all 0.2s ease;

    &:focus {
      outline: none;
      border-color: #667eea;
    }
  }

  textarea {
    min-height: 100px;
    resize: vertical;
  }
`;

const ModalActions = styled.div`
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
`;

const AliasCard = ({ alias, onToggle, onDelete, onViewActivity, onEdit }) => {
  const [showEditModal, setShowEditModal] = useState(false);
  const [editData, setEditData] = useState({
    alias_name: alias.alias_name || '',
    description: alias.description || ''
  });

  const handleCopyEmail = () => {
    navigator.clipboard.writeText(alias.alias_email);
    toast.success('Email copied to clipboard!');
  };

  const handleEdit = () => {
    setShowEditModal(true);
  };

  const handleSaveEdit = () => {
    onEdit(alias.id, editData);
    setShowEditModal(false);
  };

  const isActive = alias.status === 'active';

  return (
    <>
      <Card active={isActive} provider={alias.provider}>
        <Header>
          <AliasInfo provider={alias.provider}>
            <div className="alias-email">
              {alias.alias_email}
              <button className="copy-btn" onClick={handleCopyEmail} title="Copy email">
                <FaCopy />
              </button>
            </div>
            {alias.alias_name && (
              <div className="alias-name">{alias.alias_name}</div>
            )}
            <span className="provider-badge">{alias.provider}</span>
          </AliasInfo>
          <StatusBadge active={isActive}>
            {alias.status}
          </StatusBadge>
        </Header>

        <Description>
          {alias.description || 'No description provided'}
        </Description>

        <ForwardsTo>
          <FaExternalLinkAlt className="icon" />
          <span>Forwards to: {alias.forwards_to}</span>
        </ForwardsTo>

        <Stats>
          <StatItem color="#2196f3">
            <div className="label">Received</div>
            <div className="value">{alias.emails_received}</div>
          </StatItem>
          <StatItem color="#4caf50">
            <div className="label">Forwarded</div>
            <div className="value">{alias.emails_forwarded}</div>
          </StatItem>
          <StatItem color="#f44336">
            <div className="label">Blocked</div>
            <div className="value">{alias.emails_blocked}</div>
          </StatItem>
        </Stats>

        <Actions>
          <ActionButton
            variant={isActive ? 'default' : 'success'}
            onClick={() => onToggle(alias.id)}
            title={isActive ? 'Disable alias' : 'Enable alias'}
          >
            {isActive ? <FaToggleOff /> : <FaToggleOn />}
            {isActive ? 'Disable' : 'Enable'}
          </ActionButton>
          <ActionButton
            variant="primary"
            onClick={handleEdit}
            title="Edit alias"
          >
            <FaEdit />
            Edit
          </ActionButton>
          <ActionButton
            variant="default"
            onClick={() => onViewActivity(alias)}
            title="View activity"
          >
            <FaChartLine />
            Activity
          </ActionButton>
          <ActionButton
            variant="danger"
            onClick={() => onDelete(alias.id)}
            title="Delete alias"
          >
            <FaTrash />
            Delete
          </ActionButton>
        </Actions>
      </Card>

      {showEditModal && (
        <EditModal onClick={() => setShowEditModal(false)}>
          <ModalContent onClick={(e) => e.stopPropagation()}>
            <h3>Edit Alias</h3>
            <FormGroup>
              <label>Alias Name</label>
              <input
                type="text"
                value={editData.alias_name}
                onChange={(e) => setEditData({ ...editData, alias_name: e.target.value })}
                placeholder="e.g., Shopping Account"
              />
            </FormGroup>
            <FormGroup>
              <label>Description</label>
              <textarea
                value={editData.description}
                onChange={(e) => setEditData({ ...editData, description: e.target.value })}
                placeholder="What is this alias used for?"
              />
            </FormGroup>
            <ModalActions>
              <ActionButton
                variant="default"
                onClick={() => setShowEditModal(false)}
              >
                Cancel
              </ActionButton>
              <ActionButton
                variant="primary"
                onClick={handleSaveEdit}
              >
                Save Changes
              </ActionButton>
            </ModalActions>
          </ModalContent>
        </EditModal>
      )}
    </>
  );
};

export default AliasCard;

