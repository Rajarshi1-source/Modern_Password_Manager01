import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import { FaDice, FaCopy, FaCheck } from 'react-icons/fa';
import { motion } from 'framer-motion';
import { copyToClipboard } from '../../utils/clipboard';
import PasswordStrengthMeter from './PasswordStrengthMeter';
import QuantumDiceButton from './QuantumDiceButton';
import QuantumCertificateModal from './QuantumCertificateModal';
import GeneticDiceButton from './GeneticDiceButton';
import GeneticCertificateModal from './GeneticCertificateModal';
import DNAConnectorModal from './DNAConnectorModal';

const Container = styled.div`
  background: ${props => props.theme.cardBg};
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
`;

const PasswordDisplay = styled.div`
  background: ${props => props.theme.backgroundSecondary};
  padding: 16px;
  border-radius: 6px;
  font-family: 'Courier New', monospace;
  font-size: 18px;
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  letter-spacing: 0.05em;
  word-break: break-all;
`;

const PasswordText = styled.div`
  flex: 1;
`;

const QuantumBadge = styled.span`
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-size: 10px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 4px;
  margin-left: 8px;
  cursor: pointer;
  
  &:hover {
    opacity: 0.9;
  }
`;

const GeneticBadge = styled.span`
  background: linear-gradient(135deg, #10B981 0%, #047857 100%);
  color: white;
  font-size: 10px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 4px;
  margin-left: 8px;
  cursor: pointer;
  
  &:hover {
    opacity: 0.9;
  }
`;

const ActionButton = styled.button`
  background: ${props => props.primary ? props.theme.accent : 'transparent'};
  color: ${props => props.primary ? 'white' : props.theme.textSecondary};
  border: ${props => props.primary ? 'none' : `1px solid ${props.theme.borderColor}`};
  border-radius: 4px;
  padding: 8px 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    background: ${props => props.primary ? props.theme.accentHover : props.theme.backgroundHover};
  }
`;

const ButtonsContainer = styled.div`
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
`;

const OptionsContainer = styled.div`
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 20px;
`;

const OptionGroup = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const CheckboxLabel = styled.label`
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
`;

const Checkbox = styled.input`
  accent-color: ${props => props.theme.accent};
  width: 16px;
  height: 16px;
`;

const RangeLabel = styled.label`
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const RangeValue = styled.div`
  display: flex;
  justify-content: space-between;
  
  span {
    font-size: 14px;
    color: ${props => props.theme.textSecondary};
  }
`;

const Range = styled.input`
  accent-color: ${props => props.theme.accent};
  width: 100%;
`;

const CopyNotification = styled(motion.div)`
  position: absolute;
  top: 10px;
  right: 10px;
  background: ${props => props.theme.success};
  color: white;
  padding: 8px 12px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const ModeToggle = styled.div`
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  background: ${props => props.theme.backgroundSecondary};
  padding: 4px;
  border-radius: 8px;
`;

const ModeButton = styled.button`
  flex: 1;
  padding: 10px 16px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  
  ${props => props.$active ? `
    background: ${props.theme.accent || '#667eea'};
    color: white;
  ` : `
    background: transparent;
    color: ${props.theme.textSecondary};
    
    &:hover {
      background: ${props.theme.backgroundHover};
    }
  `}
`;

const PasswordGenerator = ({ onSelect }) => {
  const [password, setPassword] = useState('');
  const [length, setLength] = useState(16);
  const [options, setOptions] = useState({
    uppercase: true,
    lowercase: true,
    numbers: true,
    symbols: true,
  });
  const [copied, setCopied] = useState(false);

  // Mode: 'standard' | 'quantum' | 'genetic'
  const [mode, setMode] = useState('standard');

  // Quantum state
  const [quantumCertificate, setQuantumCertificate] = useState(null);
  const [showCertModal, setShowCertModal] = useState(false);

  // Genetic state
  const [geneticCertificate, setGeneticCertificate] = useState(null);
  const [showGeneticCertModal, setShowGeneticCertModal] = useState(false);
  const [showDNAConnector, setShowDNAConnector] = useState(false);

  // Generate password on mount and when options change (standard mode only)
  useEffect(() => {
    if (mode === 'standard') {
      generatePassword();
    }
  }, [length, options, mode]);

  const generatePassword = () => {
    const charset = {
      uppercase: 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
      lowercase: 'abcdefghijklmnopqrstuvwxyz',
      numbers: '0123456789',
      symbols: '!@#$%^&*()_+-=[]{}|;:,.<>?'
    };

    let chars = '';
    if (options.uppercase) chars += charset.uppercase;
    if (options.lowercase) chars += charset.lowercase;
    if (options.numbers) chars += charset.numbers;
    if (options.symbols) chars += charset.symbols;

    if (!chars) {
      // If no options selected, default to lowercase
      chars = charset.lowercase;
      setOptions(prev => ({ ...prev, lowercase: true }));
    }

    // Generate password using Web Crypto API for better randomness
    const randomValues = new Uint32Array(length);
    window.crypto.getRandomValues(randomValues);

    let result = '';
    for (let i = 0; i < length; i++) {
      result += chars[randomValues[i] % chars.length];
    }

    setPassword(result);
    setQuantumCertificate(null); // Clear quantum cert for standard passwords
  };

  const handleQuantumGenerate = (result) => {
    setPassword(result.password);
    setQuantumCertificate(result.certificate);
    setGeneticCertificate(null); // Clear genetic cert
  };

  const handleGeneticGenerate = (password, certificate) => {
    setPassword(password);
    setGeneticCertificate(certificate);
    setQuantumCertificate(null); // Clear quantum cert
  };

  const handleDNAConnected = () => {
    setShowDNAConnector(false);
    // Optionally auto-generate after connection
  };

  const handleOptionChange = (e) => {
    const { name, checked } = e.target;
    setOptions(prev => {
      const newOptions = { ...prev, [name]: checked };
      // Ensure at least one option is always selected
      if (!Object.values(newOptions).some(Boolean)) {
        return prev;
      }
      return newOptions;
    });
  };

  const handleCopy = () => {
    copyToClipboard(password);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleUse = () => {
    if (onSelect) {
      onSelect(password);
    }
  };

  return (
    <Container>
      {/* Mode Toggle: Standard / Quantum / Genetic */}
      <ModeToggle>
        <ModeButton
          $active={mode === 'standard'}
          onClick={() => setMode('standard')}
        >
          🎲 Standard
        </ModeButton>
        <ModeButton
          $active={mode === 'quantum'}
          onClick={() => setMode('quantum')}
        >
          ⚛️ Quantum
        </ModeButton>
        <ModeButton
          $active={mode === 'genetic'}
          onClick={() => setMode('genetic')}
        >
          🧬 Genetic
        </ModeButton>
      </ModeToggle>

      <PasswordDisplay>
        <PasswordText>{password}</PasswordText>
        {quantumCertificate && (
          <QuantumBadge onClick={() => setShowCertModal(true)}>
            ⚛️ Quantum Certified
          </QuantumBadge>
        )}
        {geneticCertificate && (
          <GeneticBadge onClick={() => setShowGeneticCertModal(true)}>
            🧬 Genetic Certified
          </GeneticBadge>
        )}
      </PasswordDisplay>

      <PasswordStrengthMeter password={password} />

      <ButtonsContainer>
        {mode === 'standard' && (
          <ActionButton onClick={generatePassword}>
            <FaDice /> Generate New
          </ActionButton>
        )}
        {mode === 'quantum' && (
          <QuantumDiceButton
            onGenerate={handleQuantumGenerate}
            length={length}
            options={options}
            showStatus={true}
            showCertificate={false}
          />
        )}
        {mode === 'genetic' && (
          <GeneticDiceButton
            onPasswordGenerated={handleGeneticGenerate}
            onCertificateView={(cert) => {
              setGeneticCertificate(cert);
              setShowGeneticCertModal(true);
            }}
            onConnectRequest={() => setShowDNAConnector(true)}
            options={{
              length,
              uppercase: options.uppercase,
              lowercase: options.lowercase,
              numbers: options.numbers,
              symbols: options.symbols,
              combineWithQuantum: true,
            }}
            showStatus={true}
            showEvolution={true}
          />
        )}
        <ActionButton onClick={handleCopy}>
          <FaCopy /> Copy
        </ActionButton>
        {onSelect && (
          <ActionButton primary onClick={handleUse}>
            Use Password
          </ActionButton>
        )}
      </ButtonsContainer>

      <OptionsContainer>
        <OptionGroup>
          <CheckboxLabel>
            <Checkbox
              type="checkbox"
              name="uppercase"
              checked={options.uppercase}
              onChange={handleOptionChange}
            />
            Uppercase (A-Z)
          </CheckboxLabel>
          <CheckboxLabel>
            <Checkbox
              type="checkbox"
              name="lowercase"
              checked={options.lowercase}
              onChange={handleOptionChange}
            />
            Lowercase (a-z)
          </CheckboxLabel>
        </OptionGroup>
        <OptionGroup>
          <CheckboxLabel>
            <Checkbox
              type="checkbox"
              name="numbers"
              checked={options.numbers}
              onChange={handleOptionChange}
            />
            Numbers (0-9)
          </CheckboxLabel>
          <CheckboxLabel>
            <Checkbox
              type="checkbox"
              name="symbols"
              checked={options.symbols}
              onChange={handleOptionChange}
            />
            Symbols (!@#$%^&*)
          </CheckboxLabel>
        </OptionGroup>
      </OptionsContainer>

      <RangeLabel>
        Password Length: {length}
        <RangeValue>
          <span>8</span>
          <span>32</span>
        </RangeValue>
        <Range
          type="range"
          min="8"
          max="32"
          value={length}
          onChange={(e) => setLength(parseInt(e.target.value))}
        />
      </RangeLabel>

      {copied && (
        <CopyNotification
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
        >
          <FaCheck /> Password copied
        </CopyNotification>
      )}

      {/* Quantum Certificate Modal */}
      <QuantumCertificateModal
        certificate={quantumCertificate}
        isOpen={showCertModal}
        onClose={() => setShowCertModal(false)}
      />

      {/* Genetic Certificate Modal */}
      <GeneticCertificateModal
        certificate={geneticCertificate}
        isOpen={showGeneticCertModal}
        onClose={() => setShowGeneticCertModal(false)}
      />

      {/* DNA Connector Modal */}
      <DNAConnectorModal
        isOpen={showDNAConnector}
        onClose={() => setShowDNAConnector(false)}
        onSuccess={handleDNAConnected}
      />
    </Container>
  );
};

export default PasswordGenerator;

