import React, { useState, useEffect } from 'react';
import styled, { keyframes } from 'styled-components';
import {
  X, Shield, Lock, Globe, Clock, Users,
  Hash, AlertTriangle, CheckCircle, Loader, Zap
} from 'lucide-react';
import fheSharingService from '../../services/fhe/fheSharingService';
import preClient, { isPreAvailable } from '../../services/fhe/preClient';
import { ensureUmbralIdentity } from '../../services/fhe/preKeyRegistration';

const fadeIn = keyframes`
  from { opacity: 0; }
  to { opacity: 1; }
`;

const slideUp = keyframes`
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
`;

const spin = keyframes`
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
`;

const Overlay = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
  animation: ${fadeIn} 0.2s ease;
`;

const Modal = styled.div`
  background: white;
  border-radius: 16px;
  width: 100%;
  max-width: 560px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  animation: ${slideUp} 0.3s ease;
`;

const ModalHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem 1.75rem;
  border-bottom: 1px solid var(--border, #eee);
`;

const ModalTitle = styled.div`
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--text-primary, #1a1a1a);
`;

const ModalIcon = styled.div`
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #4A6CF7, #7C3AED);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
`;

const CloseButton = styled.button`
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: none;
  background: var(--secondary, #f5f5f5);
  color: var(--text-secondary, #666);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;

  &:hover { background: var(--hover, #e5e5e5); color: var(--text-primary); }
`;

const ModalBody = styled.div`
  padding: 1.75rem;
`;

const FHEBanner = styled.div`
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  background: linear-gradient(135deg, rgba(74, 108, 247, 0.06), rgba(124, 58, 237, 0.06));
  border: 1px solid rgba(74, 108, 247, 0.12);
  border-radius: 12px;
  margin-bottom: 1.75rem;
  font-size: 0.85rem;
  color: var(--text-secondary, #555);
  line-height: 1.5;

  svg { flex-shrink: 0; margin-top: 2px; color: #4A6CF7; }
  strong { color: var(--text-primary, #1a1a1a); }
`;

const FormGroup = styled.div`
  margin-bottom: 1.5rem;
`;

const Label = styled.label`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary, #333);
  margin-bottom: 0.5rem;
`;

const Input = styled.input`
  width: 100%;
  padding: 0.75rem 1rem;
  border: 1.5px solid var(--border, #ddd);
  border-radius: 10px;
  font-size: 0.9rem;
  color: var(--text-primary, #1a1a1a);
  transition: border-color 0.2s, box-shadow 0.2s;
  background: var(--bg, white);
  box-sizing: border-box;

  &:focus {
    outline: none;
    border-color: #4A6CF7;
    box-shadow: 0 0 0 3px rgba(74, 108, 247, 0.1);
  }

  &::placeholder { color: var(--text-muted, #bbb); }
`;

const Select = styled.select`
  width: 100%;
  padding: 0.75rem 1rem;
  border: 1.5px solid var(--border, #ddd);
  border-radius: 10px;
  font-size: 0.9rem;
  color: var(--text-primary, #1a1a1a);
  background: var(--bg, white);
  cursor: pointer;
  box-sizing: border-box;

  &:focus {
    outline: none;
    border-color: #4A6CF7;
    box-shadow: 0 0 0 3px rgba(74, 108, 247, 0.1);
  }
`;

const DomainChips = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.5rem;
`;

const DomainChip = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.7rem;
  background: rgba(74, 108, 247, 0.08);
  color: #4A6CF7;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 500;

  button {
    background: none;
    border: none;
    color: #4A6CF7;
    cursor: pointer;
    padding: 0;
    display: flex;
    font-size: 1rem;
    line-height: 1;

    &:hover { color: #DC2626; }
  }
`;

const HelpText = styled.p`
  margin: 0.4rem 0 0;
  font-size: 0.78rem;
  color: var(--text-muted, #999);
  line-height: 1.4;
`;

const ModalFooter = styled.div`
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1.25rem 1.75rem;
  border-top: 1px solid var(--border, #eee);
`;

const Button = styled.button`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.7rem 1.5rem;
  border-radius: 10px;
  font-weight: 600;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s;
  border: ${p => p.$primary ? 'none' : '1px solid var(--border, #ddd)'};
  background: ${p => p.$primary
    ? 'linear-gradient(135deg, #4A6CF7, #6366F1)'
    : 'white'};
  color: ${p => p.$primary ? 'white' : 'var(--text-primary, #333)'};

  &:hover {
    transform: translateY(-1px);
    box-shadow: ${p => p.$primary
      ? '0 4px 14px rgba(74, 108, 247, 0.35)'
      : '0 2px 6px rgba(0, 0, 0, 0.08)'};
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }
`;

const ErrorText = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.15);
  border-radius: 10px;
  color: #B91C1C;
  font-size: 0.85rem;
  margin-bottom: 1rem;
`;

const SpinnerIcon = styled(Loader)`
  animation: ${spin} 1s linear infinite;
`;


function CreateHomomorphicShareModal({ onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    recipientUsername: '',
    vaultItemId: '',
    domainInput: '',
    domains: [],
    expiryPreset: '72h',
    maxUses: '',
    passwordForUmbral: '',
    useUmbral: false,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [preSupported, setPreSupported] = useState(false);

  useEffect(() => {
    let cancelled = false;
    isPreAvailable().then((ok) => {
      if (!cancelled) setPreSupported(ok);
    });
    return () => { cancelled = true; };
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setError(null);
  };

  const addDomain = () => {
    const domain = formData.domainInput.trim().toLowerCase();
    if (!domain || domain.length < 3) return;
    if (formData.domains.includes(domain)) return;
    setFormData(prev => ({
      ...prev,
      domains: [...prev.domains, domain],
      domainInput: '',
    }));
  };

  const removeDomain = (domain) => {
    setFormData(prev => ({
      ...prev,
      domains: prev.domains.filter(d => d !== domain),
    }));
  };

  const handleDomainKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addDomain();
    }
  };

  const getExpiresAt = () => {
    const preset = formData.expiryPreset;
    if (preset === 'none') return null;
    const now = new Date();
    const hours = { '1h': 1, '24h': 24, '72h': 72, '7d': 168, '30d': 720, '90d': 2160 };
    if (hours[preset]) {
      now.setHours(now.getHours() + hours[preset]);
      return now.toISOString();
    }
    return null;
  };

  const handleSubmit = async () => {
    if (!formData.vaultItemId.trim()) {
      setError('Please enter the Vault Item ID');
      return;
    }
    if (!formData.recipientUsername.trim()) {
      setError('Please enter the recipient username');
      return;
    }
    if (formData.domains.length === 0) {
      setError('Add at least one domain for domain binding');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      if (formData.useUmbral) {
        if (!preSupported) {
          setError('Umbral PRE is not available in this browser. Missing @nucypher/umbral-pre WASM.');
          setLoading(false);
          return;
        }
        if (!formData.passwordForUmbral) {
          setError('The plaintext password is required for the client-side PRE flow.');
          setLoading(false);
          return;
        }

        const identity = await ensureUmbralIdentity({ autoEnroll: true });
        if (!identity.ready) {
          setError(
            identity.reason === 'locked'
              ? 'Unlock your vault first so the PRE key can be used.'
              : 'Umbral identity not available. Try reloading the page.'
          );
          setLoading(false);
          return;
        }

        let recipientKeyResp;
        try {
          recipientKeyResp = await fheSharingService.fetchUmbralPublicKey(
            formData.recipientUsername.trim()
          );
        } catch (err) {
          if (err?.error === 'recipient_not_enrolled') {
            setError(
              `${formData.recipientUsername} has not enrolled an Umbral key yet. ` +
              'Ask them to open the Homomorphic Sharing dashboard first.'
            );
          } else {
            setError(err?.error || 'Failed to fetch recipient key');
          }
          setLoading(false);
          return;
        }

        const { capsule, ciphertext } = await preClient.encryptFor(
          identity.publicKeys.umbralPublicKey,
          formData.passwordForUmbral,
        );
        const kfrag = await preClient.generateKfrag({
          ownerSkBytes: identity.rawSecrets.sk,
          signerSkBytes: identity.rawSecrets.signerSk,
          recipientPkB64: recipientKeyResp.umbral_public_key,
        });

        await fheSharingService.createUmbralShare({
          vaultItemId: formData.vaultItemId.trim(),
          recipientUsername: formData.recipientUsername.trim(),
          domainConstraints: formData.domains,
          expiresAt: getExpiresAt(),
          maxUses: formData.maxUses ? parseInt(formData.maxUses, 10) : null,
          capsule,
          ciphertext,
          kfrag,
          delegatingPk: identity.publicKeys.umbralPublicKey,
          verifyingPk: identity.publicKeys.umbralVerifyingKey,
          receivingPk: recipientKeyResp.umbral_public_key,
        });
      } else {
        await fheSharingService.createShare(
          formData.vaultItemId.trim(),
          formData.recipientUsername.trim(),
          {
            domainConstraints: formData.domains,
            expiresAt: getExpiresAt(),
            maxUses: formData.maxUses ? parseInt(formData.maxUses, 10) : null,
          }
        );
      }
      onSuccess();
    } catch (err) {
      setError(err.error || err.details?.vault_item_id?.[0] || 'Failed to create share');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Overlay onClick={onClose}>
      <Modal onClick={e => e.stopPropagation()}>
        <ModalHeader>
          <ModalTitle>
            <ModalIcon><Shield size={20} /></ModalIcon>
            Create Homomorphic Share
          </ModalTitle>
          <CloseButton onClick={onClose}><X size={18} /></CloseButton>
        </ModalHeader>

        <ModalBody>
          <FHEBanner>
            <Lock size={18} />
            <div>
              <strong>FHE-Encrypted Autofill Token</strong><br />
              The recipient will receive an encrypted token that lets them autofill the password
              into web forms — but they <strong>cannot decrypt or view</strong> the password itself.
            </div>
          </FHEBanner>

          {error && (
            <ErrorText>
              <AlertTriangle size={16} />
              {error}
            </ErrorText>
          )}

          <FormGroup>
            <Label><Lock size={14} /> Vault Item ID</Label>
            <Input
              name="vaultItemId"
              value={formData.vaultItemId}
              onChange={handleChange}
              placeholder="UUID of the password to share"
            />
            <HelpText>The UUID identifier of the password item in your vault.</HelpText>
          </FormGroup>

          <FormGroup>
            <Label><Users size={14} /> Recipient Username</Label>
            <Input
              name="recipientUsername"
              value={formData.recipientUsername}
              onChange={handleChange}
              placeholder="e.g., john.doe"
            />
            <HelpText>The user who will be able to autofill (but not see) the password.</HelpText>
          </FormGroup>

          <FormGroup>
            <Label><Globe size={14} /> Domain Binding</Label>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <Input
                name="domainInput"
                value={formData.domainInput}
                onChange={handleChange}
                onKeyDown={handleDomainKeyDown}
                placeholder="e.g., github.com"
                style={{ flex: 1 }}
              />
              <Button onClick={addDomain} type="button" style={{ whiteSpace: 'nowrap' }}>
                Add
              </Button>
            </div>
            {formData.domains.length > 0 && (
              <DomainChips>
                {formData.domains.map(domain => (
                  <DomainChip key={domain}>
                    <Globe size={12} />
                    {domain}
                    <button onClick={() => removeDomain(domain)} aria-label={`Remove ${domain}`}>×</button>
                  </DomainChip>
                ))}
              </DomainChips>
            )}
            <HelpText>
              Autofill will only work on these domains. Domain binding is required for security.
            </HelpText>
          </FormGroup>

          <FormGroup>
            <Label><Clock size={14} /> Expiration</Label>
            <Select name="expiryPreset" value={formData.expiryPreset} onChange={handleChange}>
              <option value="1h">1 hour</option>
              <option value="24h">24 hours</option>
              <option value="72h">3 days (default)</option>
              <option value="7d">7 days</option>
              <option value="30d">30 days</option>
              <option value="90d">90 days</option>
              <option value="none">No expiration</option>
            </Select>
          </FormGroup>

          <FormGroup>
            <Label><Hash size={14} /> Max Uses (optional)</Label>
            <Input
              name="maxUses"
              type="number"
              min="1"
              max="10000"
              value={formData.maxUses}
              onChange={handleChange}
              placeholder="Leave empty for unlimited"
            />
            <HelpText>Limit how many times the recipient can autofill. Empty = unlimited.</HelpText>
          </FormGroup>

          <FormGroup>
            <Label>
              <Zap size={14} /> Cryptographic backbone
            </Label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <input
                id="useUmbral"
                type="checkbox"
                checked={formData.useUmbral}
                onChange={(e) => setFormData((p) => ({ ...p, useUmbral: e.target.checked }))}
                disabled={!preSupported}
              />
              <label htmlFor="useUmbral" style={{ fontSize: '0.85rem' }}>
                Use Umbral PRE (client-side, recipient cannot see plaintext)
              </label>
            </div>
            <HelpText>
              {preSupported
                ? "Umbral produces a real re-encryption capsule; the server can only re-encrypt it, never decrypt."
                : "Umbral WASM not available in this browser — falls back to simulated-v1."}
            </HelpText>
          </FormGroup>

          {formData.useUmbral && (
            <FormGroup>
              <Label><Lock size={14} /> Password (PRE plaintext input)</Label>
              <Input
                name="passwordForUmbral"
                type="password"
                value={formData.passwordForUmbral}
                onChange={handleChange}
                placeholder="Plaintext to encrypt under your Umbral public key"
                autoComplete="off"
              />
              <HelpText>
                Never leaves this browser. Umbral encrypts it with your public key before it is uploaded.
              </HelpText>
            </FormGroup>
          )}
        </ModalBody>

        <ModalFooter>
          <Button onClick={onClose} disabled={loading}>Cancel</Button>
          <Button $primary onClick={handleSubmit} disabled={loading}>
            {loading ? (
              <><SpinnerIcon size={16} /> Encrypting...</>
            ) : (
              <><Zap size={16} /> Create FHE Share</>
            )}
          </Button>
        </ModalFooter>
      </Modal>
    </Overlay>
  );
}

export default CreateHomomorphicShareModal;
