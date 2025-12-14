import React, { useState } from 'react';
import styled, { keyframes } from 'styled-components';
import { FaEye, FaEyeSlash, FaArrowLeft, FaSave, FaTrash, FaRandom, FaKey, FaGlobe, FaUser, FaStickyNote, FaTimes, FaLock } from 'react-icons/fa';
import { useFormik } from 'formik';
import * as Yup from 'yup';
import PasswordGenerator from '../security/PasswordGenerator';

// Animations
const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
`;

// Colors matching vault page
const colors = {
  primary: '#7B68EE',
  primaryDark: '#6B58DE',
  primaryLight: '#9B8BFF',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  background: '#f8f9ff',
  backgroundSecondary: '#ffffff',
  cardBg: '#ffffff',
  text: '#1a1a2e',
  textSecondary: '#6b7280',
  border: '#e8e4ff',
  borderLight: '#d4ccff'
};

const FormContainer = styled.div`
  max-width: 580px;
  width: 100%;
  margin: 0 auto;
  padding: 24px;
  animation: ${fadeIn} 0.4s ease-out;
`;

const FormHeader = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid ${colors.border};
`;

const BackButton = styled.button`
  background: ${colors.background};
  border: 2px solid ${colors.border};
  color: ${colors.textSecondary};
  cursor: pointer;
  padding: 12px;
  border-radius: 12px;
  transition: all 0.25s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  
  &:hover {
    background: ${colors.border};
    color: ${colors.primary};
    border-color: ${colors.primary};
    transform: translateX(-4px);
  }
`;

const HeaderContent = styled.div`
  flex: 1;
`;

const Title = styled.h2`
  margin: 0 0 4px 0;
  font-size: 24px;
  font-weight: 700;
  color: ${colors.text};
  display: flex;
  align-items: center;
  gap: 12px;
`;

const TitleIcon = styled.div`
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, ${colors.primary}20 0%, ${colors.primaryLight}15 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  
  svg {
    font-size: 20px;
    color: ${colors.primary};
  }
`;

const Subtitle = styled.p`
  margin: 0;
  font-size: 14px;
  color: ${colors.textSecondary};
`;

const Form = styled.form`
  display: flex;
  flex-direction: column;
  gap: 20px;
`;

const FormSection = styled.div`
  background: linear-gradient(135deg, ${colors.background} 0%, ${colors.border}30 100%);
  border-radius: 16px;
  padding: 20px;
`;

const SectionTitle = styled.h3`
  font-size: 13px;
  font-weight: 700;
  color: ${colors.textSecondary};
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0 0 16px 0;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const FieldGroup = styled.div`
  margin-bottom: 16px;
  
  &:last-child {
    margin-bottom: 0;
  }
`;

const LabelWrapper = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
`;

const LabelIcon = styled.div`
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, ${colors.primary}15 0%, ${colors.primaryLight}10 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  
  svg {
    font-size: 14px;
    color: ${colors.primary};
  }
`;

const Label = styled.label`
  font-size: 14px;
  font-weight: 600;
  color: ${colors.text};
`;

const RequiredStar = styled.span`
  color: ${colors.danger};
  margin-left: 4px;
`;

const InputWrapper = styled.div`
  position: relative;
`;

const Input = styled.input`
  width: 100%;
  padding: 14px 16px;
  border-radius: 12px;
  border: 2px solid ${props => props.error ? colors.danger : colors.border};
  background: ${colors.backgroundSecondary};
  color: ${colors.text};
  font-size: 15px;
  font-weight: 500;
  transition: all 0.25s ease;
  box-sizing: border-box;
  
  &:focus {
    outline: none;
    border-color: ${props => props.error ? colors.danger : colors.primary};
    background: ${colors.background};
    box-shadow: 0 0 0 4px ${props => props.error ? `${colors.danger}15` : `${colors.primary}15`};
  }
  
  &::placeholder {
    color: ${colors.textSecondary};
    font-weight: 400;
  }
`;

const PasswordActions = styled.div`
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  gap: 4px;
`;

const ActionIconButton = styled.button`
  background: ${colors.background};
  border: 1px solid ${colors.border};
  color: ${colors.textSecondary};
  cursor: pointer;
  padding: 8px;
  border-radius: 8px;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  
  &:hover {
    color: ${colors.primary};
    background: ${colors.border};
    border-color: ${colors.borderLight};
  }
`;

const GeneratePasswordButton = styled.button`
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  background: linear-gradient(135deg, ${colors.primary}10 0%, ${colors.primaryLight}08 100%);
  border: 2px dashed ${colors.border};
  color: ${colors.primary};
  padding: 14px 20px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  margin-top: 12px;
  cursor: pointer;
  transition: all 0.25s ease;
  
  &:hover {
    background: linear-gradient(135deg, ${colors.primary}15 0%, ${colors.primaryLight}12 100%);
    border-color: ${colors.primary};
    transform: translateY(-2px);
  }
`;

const TextArea = styled.textarea`
  width: 100%;
  padding: 14px 16px;
  border-radius: 12px;
  border: 2px solid ${props => props.error ? colors.danger : colors.border};
  background: ${colors.backgroundSecondary};
  color: ${colors.text};
  font-size: 15px;
  font-weight: 500;
  font-family: inherit;
  min-height: 100px;
  resize: vertical;
  transition: all 0.25s ease;
  box-sizing: border-box;
  line-height: 1.6;
  
  &:focus {
    outline: none;
    border-color: ${colors.primary};
    background: ${colors.background};
    box-shadow: 0 0 0 4px ${colors.primary}15;
  }
  
  &::placeholder {
    color: ${colors.textSecondary};
    font-weight: 400;
  }
`;

const ErrorMessage = styled.div`
  color: ${colors.danger};
  font-size: 13px;
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
`;

const ButtonsContainer = styled.div`
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 8px;
  padding-top: 20px;
  border-top: 1px solid ${colors.border};
`;

const Button = styled.button`
  padding: 14px 28px;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  transition: all 0.3s ease;
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

const SaveButton = styled(Button)`
  background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%);
  color: white;
  border: none;
  box-shadow: 0 4px 14px ${colors.primary}40;
  flex: 1;
  justify-content: center;
  
  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px ${colors.primary}50;
  }
`;

const DeleteButton = styled(Button)`
  background: ${colors.danger}10;
  color: ${colors.danger};
  border: 2px solid ${colors.danger}30;
  
  &:hover:not(:disabled) {
    background: ${colors.danger}20;
    border-color: ${colors.danger};
  }
`;

const ModalOverlay = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: ${fadeIn} 0.2s ease-out;
`;

const ModalContent = styled.div`
  background: ${colors.cardBg};
  border-radius: 20px;
  padding: 28px;
  max-width: 480px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  position: relative;
`;

const ModalClose = styled.button`
  position: absolute;
  top: 16px;
  right: 16px;
  background: ${colors.background};
  border: 1px solid ${colors.border};
  color: ${colors.textSecondary};
  cursor: pointer;
  padding: 10px;
  border-radius: 10px;
  transition: all 0.2s ease;
  
  &:hover {
    color: ${colors.danger};
    background: ${colors.danger}15;
    border-color: ${colors.danger}40;
  }
`;

const PasswordForm = ({ initialData = {}, onSubmit, onDelete, onCancel }) => {
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [showGenerator, setShowGenerator] = useState(false);
  
  const formik = useFormik({
    initialValues: {
      name: initialData.name || '',
      username: initialData.username || '',
      password: initialData.password || '',
      url: initialData.url || '',
      notes: initialData.notes || '',
    },
    validationSchema: Yup.object({
      name: Yup.string().required('Name is required'),
      password: Yup.string().required('Password is required'),
    }),
    onSubmit: (values) => {
      onSubmit({
        ...initialData,
        type: 'password',
        data: values,
      });
    },
  });
  
  const togglePasswordVisibility = () => {
    setPasswordVisible(!passwordVisible);
  };
  
  const handleSelectPassword = (generatedPassword) => {
    formik.setFieldValue('password', generatedPassword);
    setShowGenerator(false);
  };
  
  return (
    <FormContainer>
      <FormHeader>
        <BackButton onClick={onCancel} type="button">
          <FaArrowLeft />
        </BackButton>
        <TitleIcon>
          <FaKey />
        </TitleIcon>
        <HeaderContent>
          <Title>{initialData.id ? 'Edit Password' : 'Add Password'}</Title>
          <Subtitle>Securely store your login credentials</Subtitle>
        </HeaderContent>
      </FormHeader>
      
      <Form onSubmit={formik.handleSubmit}>
        <FormSection>
          <SectionTitle>📝 Basic Info</SectionTitle>
          
          <FieldGroup>
            <LabelWrapper>
              <LabelIcon><FaLock /></LabelIcon>
              <Label htmlFor="name">Name<RequiredStar>*</RequiredStar></Label>
            </LabelWrapper>
            <Input
              id="name"
              name="name"
              type="text"
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              value={formik.values.name}
              error={formik.touched.name && formik.errors.name}
              placeholder="e.g., Gmail Account"
            />
            {formik.touched.name && formik.errors.name && (
              <ErrorMessage>{formik.errors.name}</ErrorMessage>
            )}
          </FieldGroup>
          
          <FieldGroup>
            <LabelWrapper>
              <LabelIcon><FaGlobe /></LabelIcon>
              <Label htmlFor="url">Website URL</Label>
            </LabelWrapper>
            <Input
              id="url"
              name="url"
              type="text"
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              value={formik.values.url}
              placeholder="e.g., https://example.com"
            />
          </FieldGroup>
        </FormSection>
        
        <FormSection>
          <SectionTitle>🔐 Credentials</SectionTitle>
          
          <FieldGroup>
            <LabelWrapper>
              <LabelIcon><FaUser /></LabelIcon>
              <Label htmlFor="username">Username / Email</Label>
            </LabelWrapper>
            <Input
              id="username"
              name="username"
              type="text"
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              value={formik.values.username}
              placeholder="e.g., user@example.com"
            />
          </FieldGroup>
          
          <FieldGroup>
            <LabelWrapper>
              <LabelIcon><FaLock /></LabelIcon>
              <Label htmlFor="password">Password<RequiredStar>*</RequiredStar></Label>
            </LabelWrapper>
            <InputWrapper>
              <Input
                id="password"
                name="password"
                type={passwordVisible ? 'text' : 'password'}
                onChange={formik.handleChange}
                onBlur={formik.handleBlur}
                value={formik.values.password}
                error={formik.touched.password && formik.errors.password}
                style={{ paddingRight: '90px' }}
              />
              <PasswordActions>
                <ActionIconButton 
                  type="button" 
                  onClick={() => setShowGenerator(true)} 
                  title="Generate Password"
                >
                  <FaRandom />
                </ActionIconButton>
                <ActionIconButton 
                  type="button" 
                  onClick={togglePasswordVisibility} 
                  title={passwordVisible ? 'Hide Password' : 'Show Password'}
                >
                  {passwordVisible ? <FaEyeSlash /> : <FaEye />}
                </ActionIconButton>
              </PasswordActions>
            </InputWrapper>
            {formik.touched.password && formik.errors.password && (
              <ErrorMessage>{formik.errors.password}</ErrorMessage>
            )}
            
            <GeneratePasswordButton 
              type="button"
              onClick={() => setShowGenerator(true)}
            >
              <FaRandom /> Generate Strong Password
            </GeneratePasswordButton>
          </FieldGroup>
        </FormSection>
        
        <FormSection>
          <SectionTitle>📋 Additional Info</SectionTitle>
          
          <FieldGroup>
            <LabelWrapper>
              <LabelIcon><FaStickyNote /></LabelIcon>
              <Label htmlFor="notes">Notes (Optional)</Label>
            </LabelWrapper>
            <TextArea
              id="notes"
              name="notes"
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              value={formik.values.notes}
              placeholder="Additional information..."
            />
          </FieldGroup>
        </FormSection>
        
        <ButtonsContainer>
          {initialData.id && (
            <DeleteButton type="button" onClick={() => onDelete(initialData.id)}>
              <FaTrash /> Delete
            </DeleteButton>
          )}
          <SaveButton type="submit" disabled={formik.isSubmitting || !formik.isValid}>
            <FaSave /> {initialData.id ? 'Update Password' : 'Save Password'}
          </SaveButton>
        </ButtonsContainer>
      </Form>
      
      {showGenerator && (
        <ModalOverlay onClick={() => setShowGenerator(false)}>
          <ModalContent onClick={e => e.stopPropagation()}>
            <ModalClose onClick={() => setShowGenerator(false)}>
              <FaTimes />
            </ModalClose>
            <PasswordGenerator onSelect={handleSelectPassword} />
          </ModalContent>
        </ModalOverlay>
      )}
    </FormContainer>
  );
};

export default PasswordForm;
