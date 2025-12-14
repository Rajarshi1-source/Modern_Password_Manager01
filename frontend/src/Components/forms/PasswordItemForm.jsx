import React, { useState } from 'react';
import styled, { keyframes } from 'styled-components';
import { Formik, Form, Field, ErrorMessage } from 'formik';
import * as Yup from 'yup';
import { FaEye, FaEyeSlash, FaRandom, FaLock, FaGlobe, FaUser, FaEnvelope, FaStickyNote, FaTimes } from 'react-icons/fa';
import PasswordGenerator from '../PasswordGenerator';

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
  max-width: 520px;
  width: 100%;
  animation: ${fadeIn} 0.4s ease-out;
`;

const FieldGroup = styled.div`
  margin-bottom: 20px;
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

const StyledInput = styled(Field)`
  width: 100%;
  padding: 14px 16px;
  border-radius: 12px;
  border: 2px solid ${colors.border};
  background: ${colors.backgroundSecondary};
  color: ${colors.text};
  font-size: 15px;
  font-weight: 500;
  transition: all 0.25s ease;
  box-sizing: border-box;
  
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

const Textarea = styled(StyledInput).attrs({ as: 'textarea' })`
  min-height: 120px;
  resize: vertical;
  font-family: inherit;
  line-height: 1.6;
`;

const ErrorText = styled.div`
  color: ${colors.danger};
  font-size: 13px;
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
`;

const PasswordContainer = styled.div`
  position: relative;
`;

const PasswordActions = styled.div`
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  gap: 4px;
`;

const PasswordButton = styled.button`
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

const SubmitButton = styled.button`
  width: 100%;
  padding: 16px;
  background: linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%);
  color: white;
  border: none;
  border-radius: 14px;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 14px ${colors.primary}40;
  margin-top: 8px;
  
  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px ${colors.primary}50;
  }
  
  &:disabled {
    background: ${colors.textSecondary};
    cursor: not-allowed;
    box-shadow: none;
    opacity: 0.6;
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

const FormSection = styled.div`
  background: linear-gradient(135deg, ${colors.background} 0%, ${colors.border}30 100%);
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 20px;
`;

const SectionTitle = styled.h3`
  font-size: 14px;
  font-weight: 700;
  color: ${colors.textSecondary};
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0 0 16px 0;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const PasswordItemForm = ({ initialValues = {}, onSubmit, onCancel }) => {
  const [showPassword, setShowPassword] = useState(false);
  const [showGenerator, setShowGenerator] = useState(false);
  
  const defaultValues = {
    name: '',
    url: '',
    username: '',
    email: '',
    password: '',
    notes: '',
    ...initialValues
  };
  
  const validationSchema = Yup.object({
    name: Yup.string().required('Name is required'),
    password: Yup.string().required('Password is required'),
    username: Yup.string().when('email', {
      is: email => !email || email.length === 0,
      then: Yup.string().required('Username or email is required'),
    }),
    email: Yup.string().when('username', {
      is: username => !username || username.length === 0,
      then: Yup.string().email('Invalid email format').required('Username or email is required'),
    }),
  });
  
  const handlePasswordSelect = (password, formikProps) => {
    formikProps.setFieldValue('password', password);
    setShowGenerator(false);
  };
  
  return (
    <FormContainer>
      <Formik
        initialValues={defaultValues}
        validationSchema={validationSchema}
        onSubmit={onSubmit}
      >
        {formikProps => (
          <Form>
            <FormSection>
              <SectionTitle>📝 Basic Info</SectionTitle>
              
              <FieldGroup>
                <LabelWrapper>
                  <LabelIcon><FaLock /></LabelIcon>
                  <Label htmlFor="name">Item Name</Label>
                </LabelWrapper>
                <StyledInput name="name" type="text" placeholder="e.g., Google Account" />
                <ErrorMessage name="name" component={ErrorText} />
              </FieldGroup>
              
              <FieldGroup>
                <LabelWrapper>
                  <LabelIcon><FaGlobe /></LabelIcon>
                  <Label htmlFor="url">Website URL</Label>
                </LabelWrapper>
                <StyledInput name="url" type="text" placeholder="https://example.com" />
                <ErrorMessage name="url" component={ErrorText} />
              </FieldGroup>
            </FormSection>
            
            <FormSection>
              <SectionTitle>🔐 Credentials</SectionTitle>
              
              <FieldGroup>
                <LabelWrapper>
                  <LabelIcon><FaUser /></LabelIcon>
                  <Label htmlFor="username">Username</Label>
                </LabelWrapper>
                <StyledInput name="username" type="text" placeholder="Your username" />
                <ErrorMessage name="username" component={ErrorText} />
              </FieldGroup>
              
              <FieldGroup>
                <LabelWrapper>
                  <LabelIcon><FaEnvelope /></LabelIcon>
                  <Label htmlFor="email">Email</Label>
                </LabelWrapper>
                <StyledInput name="email" type="email" placeholder="email@example.com" />
                <ErrorMessage name="email" component={ErrorText} />
              </FieldGroup>
              
              <FieldGroup>
                <LabelWrapper>
                  <LabelIcon><FaLock /></LabelIcon>
                  <Label htmlFor="password">Password</Label>
                </LabelWrapper>
                <PasswordContainer>
                  <StyledInput 
                    name="password" 
                    type={showPassword ? "text" : "password"} 
                    placeholder="Your secure password"
                    style={{ paddingRight: '90px' }}
                  />
                  <PasswordActions>
                    <PasswordButton 
                      type="button" 
                      onClick={() => setShowPassword(!showPassword)}
                    >
                      {showPassword ? <FaEyeSlash /> : <FaEye />}
                    </PasswordButton>
                  </PasswordActions>
                </PasswordContainer>
                <ErrorMessage name="password" component={ErrorText} />
                
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
                  <Label htmlFor="notes">Notes</Label>
                </LabelWrapper>
                <Textarea name="notes" placeholder="Additional information..." />
                <ErrorMessage name="notes" component={ErrorText} />
              </FieldGroup>
            </FormSection>
            
            <SubmitButton type="submit" disabled={formikProps.isSubmitting}>
              {initialValues.id ? '💾 Update Password' : '💾 Save Password'}
            </SubmitButton>
            
            {showGenerator && (
              <ModalOverlay onClick={() => setShowGenerator(false)}>
                <ModalContent onClick={e => e.stopPropagation()}>
                  <ModalClose onClick={() => setShowGenerator(false)}>
                    <FaTimes />
                  </ModalClose>
                  <PasswordGenerator 
                    onSelectPassword={(password) => handlePasswordSelect(password, formikProps)} 
                  />
                </ModalContent>
              </ModalOverlay>
            )}
          </Form>
        )}
      </Formik>
    </FormContainer>
  );
};

export default PasswordItemForm;
