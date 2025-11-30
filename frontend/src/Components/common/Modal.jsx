import React, { useEffect, useRef } from 'react';
import styled from 'styled-components';
import { createPortal } from 'react-dom';
import { FaTimes } from 'react-icons/fa';
import { useAccessibility } from '../../contexts/AccessibilityContext';

const Overlay = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(2px);
  animation: fadeIn 0.2s ease-out;
  
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
`;

const ModalContainer = styled.div`
  background-color: ${props => props.theme.cardBg};
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  width: ${props => props.width || '500px'};
  max-width: 95%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  animation: slideIn 0.3s ease-out;
  position: relative;
  overflow: hidden;
  
  @keyframes slideIn {
    from {
      transform: translateY(20px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }
  
  @media (max-width: 600px) {
    width: 95%;
    max-height: 80vh;
  }
`;

const ModalHeader = styled.div`
  padding: 16px 20px;
  border-bottom: 1px solid ${props => props.theme.borderColor};
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const Title = styled.h2`
  margin: 0;
  font-size: 18px;
  color: ${props => props.theme.textPrimary};
`;

const CloseButton = styled.button`
  background: none;
  border: none;
  cursor: pointer;
  color: ${props => props.theme.textSecondary};
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  border-radius: 4px;
  transition: all 0.2s;
  
  &:hover {
    background-color: ${props => props.theme.bgHover};
    color: ${props => props.theme.textPrimary};
  }
  
  &:focus-visible {
    outline: 2px solid ${props => props.theme.primary};
    outline-offset: 2px;
  }
`;

const ModalContent = styled.div`
  padding: 20px;
  overflow-y: auto;
`;

const Modal = ({ 
  isOpen, 
  onClose, 
  title, 
  children, 
  width,
  ariaLabelledBy = 'modal-title',
  ariaDescribedBy
}) => {
  const modalRef = useRef(null);
  const { trapFocus } = useAccessibility();
  
  useEffect(() => {
    if (isOpen) {
      // Save previous active element to restore focus
      const previousActiveElement = document.activeElement;
      
      // Set up keyboard trap
      const handleKeyDown = trapFocus(modalRef);
      
      // Close on escape key
      const handleEscapeKey = (e) => {
        if (e.key === 'Escape') {
          onClose();
        }
        if (handleKeyDown) handleKeyDown(e);
      };
      
      document.addEventListener('keydown', handleEscapeKey);
      
      // Prevent scrolling of background content
      document.body.style.overflow = 'hidden';
      
      return () => {
        document.removeEventListener('keydown', handleEscapeKey);
        document.body.style.overflow = '';
        // Restore focus when modal closes
        previousActiveElement?.focus();
      };
    }
  }, [isOpen, onClose, trapFocus]);
  
  if (!isOpen) return null;
  
  return createPortal(
    <Overlay onClick={() => onClose()}>
      <ModalContainer 
        ref={modalRef}
        width={width} 
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={ariaLabelledBy}
        aria-describedby={ariaDescribedBy}
      >
        <ModalHeader>
          <Title id="modal-title">{title}</Title>
          <CloseButton 
            onClick={onClose}
            aria-label="Close modal"
          >
            <FaTimes />
          </CloseButton>
        </ModalHeader>
        <ModalContent>
          {children}
        </ModalContent>
      </ModalContainer>
    </Overlay>,
    document.body
  );
};

export default Modal;
