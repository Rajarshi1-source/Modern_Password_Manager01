import React, { useState } from 'react';
import styled, { keyframes } from 'styled-components';
import { useFormik } from 'formik';
import * as Yup from 'yup';
import { FaArrowLeft, FaSave, FaTrash, FaCreditCard, FaEye, FaEyeSlash, FaCalendarAlt, FaLock, FaUser, FaStickyNote, FaIdCard } from 'react-icons/fa';

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

const Select = styled.select`
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
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%237B68EE' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 16px center;
  padding-right: 40px;
  
  &:focus {
    outline: none;
    border-color: ${colors.primary};
    box-shadow: 0 0 0 4px ${colors.primary}15;
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

const FieldRow = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
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

// Card type options
const CARD_TYPES = [
  { value: 'visa', label: 'Visa' },
  { value: 'mastercard', label: 'Mastercard' },
  { value: 'amex', label: 'American Express' },
  { value: 'discover', label: 'Discover' },
  { value: 'other', label: 'Other' }
];

const CardForm = ({ 
  initialData = {},
  onSubmit,
  onDelete,
  onCancel
}) => {
  const [showCardNumber, setShowCardNumber] = useState(false);
  const [showCVV, setShowCVV] = useState(false);
  
  // Generate month options
  const monthOptions = Array.from({ length: 12 }, (_, i) => {
    const month = i + 1;
    return {
      value: month.toString().padStart(2, '0'),
      label: month.toString().padStart(2, '0')
    };
  });
  
  // Generate year options
  const currentYear = new Date().getFullYear();
  const yearOptions = Array.from({ length: 21 }, (_, i) => {
    const year = currentYear + i;
    return {
      value: year.toString(),
      label: year.toString()
    };
  });
  
  const validationSchema = Yup.object({
    name: Yup.string().required('Card name is required'),
    cardholderName: Yup.string().required('Cardholder name is required'),
    cardNumber: Yup.string()
      .required('Card number is required')
      .matches(/^[0-9]{13,19}$/, 'Invalid card number format'),
    expirationMonth: Yup.string().required('Month is required'),
    expirationYear: Yup.string().required('Year is required'),
    cvv: Yup.string()
      .required('CVV is required')
      .matches(/^[0-9]{3,4}$/, 'Invalid CVV format')
  });
  
  const formik = useFormik({
    initialValues: {
      name: initialData.name || '',
      cardType: initialData.cardType || 'visa',
      cardholderName: initialData.cardholderName || '',
      cardNumber: initialData.cardNumber || '',
      expirationMonth: initialData.expirationMonth || '',
      expirationYear: initialData.expirationYear || '',
      cvv: initialData.cvv || '',
      notes: initialData.notes || ''
    },
    validationSchema,
    onSubmit: (values) => {
      onSubmit({
        ...initialData,
        type: 'card',
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
          <FaCreditCard />
        </TitleIcon>
        <HeaderContent>
          <Title>{initialData.id ? 'Edit Payment Card' : 'Add Payment Card'}</Title>
          <Subtitle>Securely store your payment card information</Subtitle>
        </HeaderContent>
      </FormHeader>
      
      <Form onSubmit={formik.handleSubmit}>
        <FormSection>
          <SectionTitle>💳 Card Details</SectionTitle>
          
          <FieldGroup>
            <LabelWrapper>
              <LabelIcon><FaIdCard /></LabelIcon>
              <Label htmlFor="name">Card Name<RequiredStar>*</RequiredStar></Label>
            </LabelWrapper>
            <Input
              id="name"
              name="name"
              placeholder="e.g., Personal Visa, Work Credit Card"
              value={formik.values.name}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              error={formik.touched.name && formik.errors.name}
            />
            {formik.touched.name && formik.errors.name && (
              <ErrorMessage>{formik.errors.name}</ErrorMessage>
            )}
          </FieldGroup>
          
          <FieldGroup>
            <LabelWrapper>
              <LabelIcon><FaCreditCard /></LabelIcon>
              <Label htmlFor="cardType">Card Type</Label>
            </LabelWrapper>
            <Select
              id="cardType"
              name="cardType"
              value={formik.values.cardType}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
            >
              {CARD_TYPES.map(type => (
                <option key={type.value} value={type.value}>{type.label}</option>
              ))}
            </Select>
          </FieldGroup>
          
          <FieldGroup>
            <LabelWrapper>
              <LabelIcon><FaUser /></LabelIcon>
              <Label htmlFor="cardholderName">Cardholder Name<RequiredStar>*</RequiredStar></Label>
            </LabelWrapper>
            <Input
              id="cardholderName"
              name="cardholderName"
              placeholder="Name as it appears on the card"
              value={formik.values.cardholderName}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              error={formik.touched.cardholderName && formik.errors.cardholderName}
            />
            {formik.touched.cardholderName && formik.errors.cardholderName && (
              <ErrorMessage>{formik.errors.cardholderName}</ErrorMessage>
            )}
          </FieldGroup>
        </FormSection>
        
        <FormSection>
          <SectionTitle>🔐 Secure Information</SectionTitle>
          
          <FieldGroup>
            <LabelWrapper>
              <LabelIcon><FaLock /></LabelIcon>
              <Label htmlFor="cardNumber">Card Number<RequiredStar>*</RequiredStar></Label>
            </LabelWrapper>
            <InputWrapper>
              <Input
                id="cardNumber"
                name="cardNumber"
                type={showCardNumber ? "text" : "password"}
                placeholder="Card number without spaces"
                value={formik.values.cardNumber}
                onChange={formik.handleChange}
                onBlur={formik.handleBlur}
                error={formik.touched.cardNumber && formik.errors.cardNumber}
                style={{ paddingRight: '50px' }}
              />
              <PasswordActions>
                <ActionIconButton type="button" onClick={() => setShowCardNumber(!showCardNumber)}>
                  {showCardNumber ? <FaEyeSlash /> : <FaEye />}
                </ActionIconButton>
              </PasswordActions>
            </InputWrapper>
            {formik.touched.cardNumber && formik.errors.cardNumber && (
              <ErrorMessage>{formik.errors.cardNumber}</ErrorMessage>
            )}
          </FieldGroup>
          
          <FieldRow>
            <FieldGroup>
              <LabelWrapper>
                <LabelIcon><FaCalendarAlt /></LabelIcon>
                <Label htmlFor="expirationMonth">Month<RequiredStar>*</RequiredStar></Label>
              </LabelWrapper>
              <Select
                id="expirationMonth"
                name="expirationMonth"
                value={formik.values.expirationMonth}
                onChange={formik.handleChange}
                onBlur={formik.handleBlur}
                error={formik.touched.expirationMonth && formik.errors.expirationMonth}
              >
                <option value="">MM</option>
                {monthOptions.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </Select>
              {formik.touched.expirationMonth && formik.errors.expirationMonth && (
                <ErrorMessage>{formik.errors.expirationMonth}</ErrorMessage>
              )}
            </FieldGroup>
            
            <FieldGroup>
              <LabelWrapper>
                <LabelIcon><FaCalendarAlt /></LabelIcon>
                <Label htmlFor="expirationYear">Year<RequiredStar>*</RequiredStar></Label>
              </LabelWrapper>
              <Select
                id="expirationYear"
                name="expirationYear"
                value={formik.values.expirationYear}
                onChange={formik.handleChange}
                onBlur={formik.handleBlur}
                error={formik.touched.expirationYear && formik.errors.expirationYear}
              >
                <option value="">YYYY</option>
                {yearOptions.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </Select>
              {formik.touched.expirationYear && formik.errors.expirationYear && (
                <ErrorMessage>{formik.errors.expirationYear}</ErrorMessage>
              )}
            </FieldGroup>
            
            <FieldGroup>
              <LabelWrapper>
                <LabelIcon><FaLock /></LabelIcon>
                <Label htmlFor="cvv">CVV<RequiredStar>*</RequiredStar></Label>
              </LabelWrapper>
              <InputWrapper>
                <Input
                  id="cvv"
                  name="cvv"
                  type={showCVV ? "text" : "password"}
                  placeholder="***"
                  value={formik.values.cvv}
                  onChange={formik.handleChange}
                  onBlur={formik.handleBlur}
                  error={formik.touched.cvv && formik.errors.cvv}
                  style={{ paddingRight: '50px' }}
                />
                <PasswordActions>
                  <ActionIconButton type="button" onClick={() => setShowCVV(!showCVV)}>
                    {showCVV ? <FaEyeSlash /> : <FaEye />}
                  </ActionIconButton>
                </PasswordActions>
              </InputWrapper>
              {formik.touched.cvv && formik.errors.cvv && (
                <ErrorMessage>{formik.errors.cvv}</ErrorMessage>
              )}
            </FieldGroup>
          </FieldRow>
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
              placeholder="Additional information about this card..."
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
            <FaSave /> {initialData.id ? 'Update Card' : 'Save Card'}
          </SaveButton>
        </ButtonsContainer>
      </Form>
    </FormContainer>
  );
};

export default CardForm;
