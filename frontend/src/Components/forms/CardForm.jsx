import React, { useState } from 'react';
import styled from 'styled-components';
import { useFormik } from 'formik';
import * as Yup from 'yup';
import { FaArrowLeft, FaSave, FaTrash, FaCreditCard, FaEye, FaEyeSlash, FaCalendarAlt, FaLock } from 'react-icons/fa';
import Input from '../common/Input';
import Button from '../common/Button';

const FormContainer = styled.div`
  padding: 20px;
`;

const FormHeader = styled.div`
  display: flex;
  align-items: center;
  margin-bottom: 24px;
`;

const BackButton = styled.button`
  background: none;
  border: none;
  color: ${props => props.theme.textSecondary};
  cursor: pointer;
  padding: 8px;
  margin-right: 8px;
  border-radius: 4px;
  
  &:hover {
    background: ${props => props.theme.backgroundHover};
  }
`;

const Title = styled.h2`
  margin: 0;
  flex: 1;
`;

const Form = styled.form`
  display: flex;
  flex-direction: column;
  gap: 16px;
`;

const FieldRow = styled.div`
  display: flex;
  gap: 16px;
  
  @media (max-width: 576px) {
    flex-direction: column;
  }
`;

const ButtonsContainer = styled.div`
  display: flex;
  justify-content: space-between;
  margin-top: 20px;
`;

const SecureField = styled.div`
  position: relative;
`;

const TextArea = styled.textarea`
  padding: 12px;
  font-family: inherit;
  font-size: 14px;
  border: 1px solid ${props => props.error ? props.theme.danger : props.theme.borderColor};
  border-radius: 6px;
  background: ${props => props.theme.inputBg};
  color: ${props => props.theme.textPrimary};
  min-height: 80px;
  resize: vertical;
  width: 100%;
  
  &:focus {
    outline: none;
    border-color: ${props => props.theme.accent};
    box-shadow: 0 0 0 2px ${props => props.theme.accentLight};
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

/**
 * Form for creating and editing payment cards
 * @param {Object} props - Component props
 * @param {Object} [props.initialData={}] - Initial data for editing
 * @param {Function} props.onSubmit - Submit handler
 * @param {Function} props.onDelete - Delete handler
 * @param {Function} props.onCancel - Cancel handler
 */
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
  
  // Generate year options (current year + 20 years)
  const currentYear = new Date().getFullYear();
  const yearOptions = Array.from({ length: 21 }, (_, i) => {
    const year = currentYear + i;
    return {
      value: year.toString(),
      label: year.toString()
    };
  });
  
  // Form validation schema
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
  
  // Initialize form
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
        <BackButton onClick={onCancel}>
          <FaArrowLeft />
        </BackButton>
        <Title>{initialData.id ? 'Edit Payment Card' : 'Add Payment Card'}</Title>
      </FormHeader>
      
      <Form onSubmit={formik.handleSubmit}>
        <Input
          id="name"
          name="name"
          label="Card Name"
          placeholder="e.g., Personal Visa, Work Credit Card"
          value={formik.values.name}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          error={formik.touched.name && Boolean(formik.errors.name)}
          errorMessage={formik.touched.name && formik.errors.name}
          leftIcon={<FaCreditCard />}
          required
        />
        
        <Input
          id="cardType"
          name="cardType"
          label="Card Type"
          type="select"
          value={formik.values.cardType}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          inputProps={{
            options: CARD_TYPES
          }}
        />
        
        <Input
          id="cardholderName"
          name="cardholderName"
          label="Cardholder Name"
          placeholder="Name as it appears on the card"
          value={formik.values.cardholderName}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          error={formik.touched.cardholderName && Boolean(formik.errors.cardholderName)}
          errorMessage={formik.touched.cardholderName && formik.errors.cardholderName}
          required
        />
        
        <SecureField>
          <Input
            id="cardNumber"
            name="cardNumber"
            type={showCardNumber ? "text" : "password"}
            label="Card Number"
            placeholder="Card number without spaces"
            value={formik.values.cardNumber}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={formik.touched.cardNumber && Boolean(formik.errors.cardNumber)}
            errorMessage={formik.touched.cardNumber && formik.errors.cardNumber}
            rightIcon={showCardNumber ? <FaEyeSlash /> : <FaEye />}
            inputProps={{
              onRightIconClick: () => setShowCardNumber(!showCardNumber)
            }}
            required
          />
        </SecureField>
        
        <FieldRow>
          <Input
            id="expirationMonth"
            name="expirationMonth"
            label="Expiration Month"
            type="select"
            value={formik.values.expirationMonth}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={formik.touched.expirationMonth && Boolean(formik.errors.expirationMonth)}
            errorMessage={formik.touched.expirationMonth && formik.errors.expirationMonth}
            leftIcon={<FaCalendarAlt />}
            inputProps={{
              options: monthOptions
            }}
            required
          />
          
          <Input
            id="expirationYear"
            name="expirationYear"
            label="Expiration Year"
            type="select"
            value={formik.values.expirationYear}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={formik.touched.expirationYear && Boolean(formik.errors.expirationYear)}
            errorMessage={formik.touched.expirationYear && formik.errors.expirationYear}
            inputProps={{
              options: yearOptions
            }}
            required
          />
          
          <Input
            id="cvv"
            name="cvv"
            type={showCVV ? "text" : "password"}
            label="CVV/CVC"
            placeholder="Security code"
            value={formik.values.cvv}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={formik.touched.cvv && Boolean(formik.errors.cvv)}
            errorMessage={formik.touched.cvv && formik.errors.cvv}
            rightIcon={showCVV ? <FaEyeSlash /> : <FaEye />}
            inputProps={{
              onRightIconClick: () => setShowCVV(!showCVV)
            }}
            required
          />
        </FieldRow>
        
        <div>
          <label htmlFor="notes" style={{ 
            display: 'block', 
            marginBottom: '6px',
            fontSize: '14px',
            fontWeight: '500'
          }}>
            Notes (Optional)
          </label>
          <TextArea
            id="notes"
            name="notes"
            placeholder="Additional information about this card..."
            value={formik.values.notes}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
          />
        </div>
        
        <ButtonsContainer>
          {initialData.id && (
            <Button 
              variant="danger"
              leftIcon={<FaTrash />}
              onClick={() => onDelete(initialData.id)}
              type="button"
            >
              Delete
            </Button>
          )}
          <Button 
            variant="primary"
            leftIcon={<FaSave />}
            type="submit"
            disabled={formik.isSubmitting}
          >
            Save Card
          </Button>
        </ButtonsContainer>
      </Form>
    </FormContainer>
  );
};

export default CardForm;
