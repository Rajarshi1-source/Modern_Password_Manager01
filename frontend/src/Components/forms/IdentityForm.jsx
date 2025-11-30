import React from 'react';
import styled from 'styled-components';
import { useFormik } from 'formik';
import * as Yup from 'yup';
import { FaArrowLeft, FaSave, FaTrash, FaUser, FaEnvelope, FaPhone, FaHome, FaIdCard } from 'react-icons/fa';
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

const ErrorMessage = styled.div`
  color: ${props => props.theme.danger};
  font-size: 12px;
  margin-top: 4px;
`;

/**
 * Form for creating and editing identity information
 * @param {Object} props - Component props
 * @param {Object} [props.initialData={}] - Initial data for editing
 * @param {Function} props.onSubmit - Submit handler
 * @param {Function} props.onDelete - Delete handler
 * @param {Function} props.onCancel - Cancel handler
 */
const IdentityForm = ({
  initialData = {},
  onSubmit,
  onDelete,
  onCancel
}) => {
  // Form validation schema
  const validationSchema = Yup.object({
    name: Yup.string().required('Name is required'),
    firstName: Yup.string().required('First name is required'),
    lastName: Yup.string().required('Last name is required'),
    email: Yup.string().email('Invalid email format').required('Email is required'),
    phone: Yup.string().matches(/^[0-9+\-() ]+$/, 'Invalid phone number format'),
    address: Yup.string()
  });
  
  // Initialize form
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
        <BackButton onClick={onCancel}>
          <FaArrowLeft />
        </BackButton>
        <Title>{initialData.id ? 'Edit Identity' : 'Add Identity'}</Title>
      </FormHeader>
      
      <Form onSubmit={formik.handleSubmit}>
        <Input
          id="name"
          name="name"
          label="Identity Name"
          placeholder="e.g., Personal ID, Driver's License"
          value={formik.values.name}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          error={formik.touched.name && Boolean(formik.errors.name)}
          errorMessage={formik.touched.name && formik.errors.name}
          leftIcon={<FaIdCard />}
          required
        />
        
        <FieldRow>
          <Input
            id="firstName"
            name="firstName"
            label="First Name"
            placeholder="First name"
            value={formik.values.firstName}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={formik.touched.firstName && Boolean(formik.errors.firstName)}
            errorMessage={formik.touched.firstName && formik.errors.firstName}
            leftIcon={<FaUser />}
            required
          />
          
          <Input
            id="lastName"
            name="lastName"
            label="Last Name"
            placeholder="Last name"
            value={formik.values.lastName}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={formik.touched.lastName && Boolean(formik.errors.lastName)}
            errorMessage={formik.touched.lastName && formik.errors.lastName}
            required
          />
        </FieldRow>
        
        <Input
          id="email"
          name="email"
          label="Email"
          type="email"
          placeholder="email@example.com"
          value={formik.values.email}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          error={formik.touched.email && Boolean(formik.errors.email)}
          errorMessage={formik.touched.email && formik.errors.email}
          leftIcon={<FaEnvelope />}
          required
        />
        
        <Input
          id="phone"
          name="phone"
          label="Phone Number"
          placeholder="e.g., +1 (555) 123-4567"
          value={formik.values.phone}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          error={formik.touched.phone && Boolean(formik.errors.phone)}
          errorMessage={formik.touched.phone && formik.errors.phone}
          leftIcon={<FaPhone />}
        />
        
        <Input
          id="address"
          name="address"
          label="Address"
          placeholder="Street address"
          value={formik.values.address}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          error={formik.touched.address && Boolean(formik.errors.address)}
          errorMessage={formik.touched.address && formik.errors.address}
          leftIcon={<FaHome />}
        />
        
        <FieldRow>
          <Input
            id="city"
            name="city"
            label="City"
            placeholder="City"
            value={formik.values.city}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
          />
          
          <Input
            id="state"
            name="state"
            label="State/Province"
            placeholder="State/Province"
            value={formik.values.state}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
          />
          
          <Input
            id="zipCode"
            name="zipCode"
            label="ZIP/Postal Code"
            placeholder="ZIP/Postal Code"
            value={formik.values.zipCode}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
          />
        </FieldRow>
        
        <Input
          id="country"
          name="country"
          label="Country"
          placeholder="Country"
          value={formik.values.country}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
        />
        
        <Input
          id="identityNumber"
          name="identityNumber"
          label="ID Number"
          placeholder="e.g., SSN, license number, passport number"
          value={formik.values.identityNumber}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
        />
        
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
            placeholder="Additional information..."
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
            Save Identity
          </Button>
        </ButtonsContainer>
      </Form>
    </FormContainer>
  );
};

export default IdentityForm;
