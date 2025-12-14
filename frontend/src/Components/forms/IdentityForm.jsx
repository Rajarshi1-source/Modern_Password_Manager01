import React from 'react';
import styled, { keyframes } from 'styled-components';
import { useFormik } from 'formik';
import * as Yup from 'yup';
import { FaArrowLeft, FaSave, FaTrash, FaUser, FaEnvelope, FaPhone, FaHome, FaIdCard, FaGlobe, FaMapMarkerAlt, FaStickyNote } from 'react-icons/fa';

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
  max-width: 620px;
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

const FieldRow = styled.div`
  display: grid;
  grid-template-columns: ${props => props.$columns || 'repeat(2, 1fr)'};
  gap: 12px;
  
  @media (max-width: 576px) {
    grid-template-columns: 1fr;
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

const IdentityForm = ({
  initialData = {},
  onSubmit,
  onDelete,
  onCancel
}) => {
  const validationSchema = Yup.object({
    name: Yup.string().required('Name is required'),
    firstName: Yup.string().required('First name is required'),
    lastName: Yup.string().required('Last name is required'),
    email: Yup.string().email('Invalid email format').required('Email is required'),
    phone: Yup.string().matches(/^[0-9+\-() ]+$/, 'Invalid phone number format'),
    address: Yup.string()
  });
  
  const formik = useFormik({
    initialValues: {
      name: initialData.name || '',
      firstName: initialData.firstName || '',
      lastName: initialData.lastName || '',
      email: initialData.email || '',
      phone: initialData.phone || '',
      address: initialData.address || '',
      city: initialData.city || '',
      state: initialData.state || '',
      zipCode: initialData.zipCode || '',
      country: initialData.country || '',
      identityNumber: initialData.identityNumber || '',
      notes: initialData.notes || ''
    },
    validationSchema,
    onSubmit: (values) => {
      onSubmit({
        ...initialData,
        type: 'identity',
        data: values
      });
    }
  });
  
  return (
    <FormContainer>
      <FormHeader>
        <BackButton onClick={onCancel} type="button">
          <FaArrowLeft />
        </BackButton>
        <TitleIcon>
          <FaIdCard />
        </TitleIcon>
        <HeaderContent>
          <Title>{initialData.id ? 'Edit Identity' : 'Add Identity'}</Title>
          <Subtitle>Securely store your personal information</Subtitle>
        </HeaderContent>
      </FormHeader>
      
      <Form onSubmit={formik.handleSubmit}>
        <FormSection>
          <SectionTitle>👤 Basic Information</SectionTitle>
          
          <FieldGroup>
            <LabelWrapper>
              <LabelIcon><FaIdCard /></LabelIcon>
              <Label htmlFor="name">Identity Name<RequiredStar>*</RequiredStar></Label>
            </LabelWrapper>
            <Input
              id="name"
              name="name"
              placeholder="e.g., Personal ID, Driver's License"
              value={formik.values.name}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              error={formik.touched.name && formik.errors.name}
            />
            {formik.touched.name && formik.errors.name && (
              <ErrorMessage>{formik.errors.name}</ErrorMessage>
            )}
          </FieldGroup>
          
          <FieldRow>
            <FieldGroup>
              <LabelWrapper>
                <LabelIcon><FaUser /></LabelIcon>
                <Label htmlFor="firstName">First Name<RequiredStar>*</RequiredStar></Label>
              </LabelWrapper>
              <Input
                id="firstName"
                name="firstName"
                placeholder="First name"
                value={formik.values.firstName}
                onChange={formik.handleChange}
                onBlur={formik.handleBlur}
                error={formik.touched.firstName && formik.errors.firstName}
              />
              {formik.touched.firstName && formik.errors.firstName && (
                <ErrorMessage>{formik.errors.firstName}</ErrorMessage>
              )}
            </FieldGroup>
            
            <FieldGroup>
              <LabelWrapper>
                <LabelIcon><FaUser /></LabelIcon>
                <Label htmlFor="lastName">Last Name<RequiredStar>*</RequiredStar></Label>
              </LabelWrapper>
              <Input
                id="lastName"
                name="lastName"
                placeholder="Last name"
                value={formik.values.lastName}
                onChange={formik.handleChange}
                onBlur={formik.handleBlur}
                error={formik.touched.lastName && formik.errors.lastName}
              />
              {formik.touched.lastName && formik.errors.lastName && (
                <ErrorMessage>{formik.errors.lastName}</ErrorMessage>
              )}
            </FieldGroup>
          </FieldRow>
        </FormSection>
        
        <FormSection>
          <SectionTitle>📧 Contact Information</SectionTitle>
          
          <FieldGroup>
            <LabelWrapper>
              <LabelIcon><FaEnvelope /></LabelIcon>
              <Label htmlFor="email">Email<RequiredStar>*</RequiredStar></Label>
            </LabelWrapper>
            <Input
              id="email"
              name="email"
              type="email"
              placeholder="email@example.com"
              value={formik.values.email}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              error={formik.touched.email && formik.errors.email}
            />
            {formik.touched.email && formik.errors.email && (
              <ErrorMessage>{formik.errors.email}</ErrorMessage>
            )}
          </FieldGroup>
          
          <FieldGroup>
            <LabelWrapper>
              <LabelIcon><FaPhone /></LabelIcon>
              <Label htmlFor="phone">Phone Number</Label>
            </LabelWrapper>
            <Input
              id="phone"
              name="phone"
              placeholder="e.g., +1 (555) 123-4567"
              value={formik.values.phone}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              error={formik.touched.phone && formik.errors.phone}
            />
            {formik.touched.phone && formik.errors.phone && (
              <ErrorMessage>{formik.errors.phone}</ErrorMessage>
            )}
          </FieldGroup>
        </FormSection>
        
        <FormSection>
          <SectionTitle>🏠 Address</SectionTitle>
          
          <FieldGroup>
            <LabelWrapper>
              <LabelIcon><FaHome /></LabelIcon>
              <Label htmlFor="address">Street Address</Label>
            </LabelWrapper>
            <Input
              id="address"
              name="address"
              placeholder="Street address"
              value={formik.values.address}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
            />
          </FieldGroup>
          
          <FieldRow $columns="repeat(3, 1fr)">
            <FieldGroup>
              <LabelWrapper>
                <LabelIcon><FaMapMarkerAlt /></LabelIcon>
                <Label htmlFor="city">City</Label>
              </LabelWrapper>
              <Input
                id="city"
                name="city"
                placeholder="City"
                value={formik.values.city}
                onChange={formik.handleChange}
                onBlur={formik.handleBlur}
              />
            </FieldGroup>
            
            <FieldGroup>
              <LabelWrapper>
                <LabelIcon><FaMapMarkerAlt /></LabelIcon>
                <Label htmlFor="state">State/Province</Label>
              </LabelWrapper>
              <Input
                id="state"
                name="state"
                placeholder="State"
                value={formik.values.state}
                onChange={formik.handleChange}
                onBlur={formik.handleBlur}
              />
            </FieldGroup>
            
            <FieldGroup>
              <LabelWrapper>
                <LabelIcon><FaMapMarkerAlt /></LabelIcon>
                <Label htmlFor="zipCode">ZIP Code</Label>
              </LabelWrapper>
              <Input
                id="zipCode"
                name="zipCode"
                placeholder="ZIP"
                value={formik.values.zipCode}
                onChange={formik.handleChange}
                onBlur={formik.handleBlur}
              />
            </FieldGroup>
          </FieldRow>
          
          <FieldGroup>
            <LabelWrapper>
              <LabelIcon><FaGlobe /></LabelIcon>
              <Label htmlFor="country">Country</Label>
            </LabelWrapper>
            <Input
              id="country"
              name="country"
              placeholder="Country"
              value={formik.values.country}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
            />
          </FieldGroup>
        </FormSection>
        
        <FormSection>
          <SectionTitle>🔐 Identification</SectionTitle>
          
          <FieldGroup>
            <LabelWrapper>
              <LabelIcon><FaIdCard /></LabelIcon>
              <Label htmlFor="identityNumber">ID Number</Label>
            </LabelWrapper>
            <Input
              id="identityNumber"
              name="identityNumber"
              placeholder="e.g., SSN, license number, passport number"
              value={formik.values.identityNumber}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
            />
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
              placeholder="Additional information..."
              value={formik.values.notes}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
            />
          </FieldGroup>
        </FormSection>
        
        <ButtonsContainer>
          {initialData.id && (
            <DeleteButton type="button" onClick={() => onDelete(initialData.id)}>
              <FaTrash /> Delete
            </DeleteButton>
          )}
          <SaveButton type="submit" disabled={formik.isSubmitting}>
            <FaSave /> {initialData.id ? 'Update Identity' : 'Save Identity'}
          </SaveButton>
        </ButtonsContainer>
      </Form>
    </FormContainer>
  );
};

export default IdentityForm;
