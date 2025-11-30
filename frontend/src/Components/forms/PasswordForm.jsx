import React, { useState } from 'react';
import styled from 'styled-components';
import { FaEye, FaEyeSlash, FaArrowLeft, FaSave, FaTrash, FaRandom } from 'react-icons/fa';
import { useFormik } from 'formik';
import * as Yup from 'yup';
import PasswordGenerator from '../security/PasswordGenerator';
import Modal from '../common/Modal';

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

const FormGroup = styled.div`
  display: flex;
  flex-direction: column;
  gap: 6px;
`;

const Label = styled.label`
  font-size: 14px;
  font-weight: 500;
`;

const Input = styled.input`
  padding: 10px 12px;
  border: 1px solid ${props => props.error ? props.theme.danger : props.theme.borderColor};
  border-radius: 4px;
  font-size: 14px;
  background: ${props => props.theme.inputBg};
  color: ${props => props.theme.textPrimary};
  
  &:focus {
    outline: none;
    border-color: ${props => props.theme.accent};
    box-shadow: 0 0 0 2px ${props => props.theme.accentLight};
  }
`;

const Textarea = styled.textarea`
  padding: 10px 12px;
  border: 1px solid ${props => props.error ? props.theme.danger : props.theme.borderColor};
  border-radius: 4px;
  font-size: 14px;
  background: ${props => props.theme.inputBg};
  color: ${props => props.theme.textPrimary};
  min-height: 80px;
  resize: vertical;
  
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

const PasswordContainer = styled.div`
  position: relative;
`;

const PasswordVisibilityToggle = styled.button`
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: ${props => props.theme.textSecondary};
  cursor: pointer;
`;

const GenerateButton = styled(PasswordVisibilityToggle)`
  right: 40px;
`;

const ButtonsContainer = styled.div`
  display: flex;
  justify-content: space-between;
  margin-top: 20px;
`;

const Button = styled.button`
  padding: 10px 20px;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
`;

const SaveButton = styled(Button)`
  background: ${props => props.theme.accent};
  color: white;
  border: none;
  
  &:hover:not(:disabled) {
    background: ${props => props.theme.accentHover};
  }
`;

const DeleteButton = styled(Button)`
  background: transparent;
  color: ${props => props.theme.danger};
  border: 1px solid ${props => props.theme.danger};
  
  &:hover:not(:disabled) {
    background: ${props => props.theme.dangerLight};
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
        <BackButton onClick={onCancel}>
          <FaArrowLeft />
        </BackButton>
        <Title>{initialData.id ? 'Edit Password' : 'Add Password'}</Title>
      </FormHeader>
      
      <Form onSubmit={formik.handleSubmit}>
        <FormGroup>
          <Label htmlFor="name">Name</Label>
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
        </FormGroup>
        
        <FormGroup>
          <Label htmlFor="username">Username / Email</Label>
          <Input
            id="username"
            name="username"
            type="text"
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            value={formik.values.username}
            error={formik.touched.username && formik.errors.username}
            placeholder="e.g., user@example.com"
          />
        </FormGroup>
        
        <FormGroup>
          <Label htmlFor="password">Password</Label>
          <PasswordContainer>
            <Input
              id="password"
              name="password"
              type={passwordVisible ? 'text' : 'password'}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              value={formik.values.password}
              error={formik.touched.password && formik.errors.password}
            />
            <GenerateButton 
              type="button" 
              onClick={() => setShowGenerator(true)} 
              title="Generate Password"
            >
              <FaRandom />
            </GenerateButton>
            <PasswordVisibilityToggle 
              type="button" 
              onClick={togglePasswordVisibility} 
              title={passwordVisible ? 'Hide Password' : 'Show Password'}
            >
              {passwordVisible ? <FaEyeSlash /> : <FaEye />}
            </PasswordVisibilityToggle>
          </PasswordContainer>
          {formik.touched.password && formik.errors.password && (
            <ErrorMessage>{formik.errors.password}</ErrorMessage>
          )}
        </FormGroup>
        
        <FormGroup>
          <Label htmlFor="url">Website URL</Label>
          <Input
            id="url"
            name="url"
            type="text"
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            value={formik.values.url}
            error={formik.touched.url && formik.errors.url}
            placeholder="e.g., https://example.com"
          />
        </FormGroup>
        
        <FormGroup>
          <Label htmlFor="notes">Notes</Label>
          <Textarea
            id="notes"
            name="notes"
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            value={formik.values.notes}
            error={formik.touched.notes && formik.errors.notes}
            placeholder="Additional information..."
          />
        </FormGroup>
        
        <ButtonsContainer>
          {initialData.id && (
            <DeleteButton 
              type="button" 
              onClick={() => onDelete(initialData.id)}
            >
              <FaTrash /> Delete
            </DeleteButton>
          )}
          <SaveButton 
            type="submit" 
            disabled={formik.isSubmitting || !formik.isValid}
          >
            <FaSave /> Save
          </SaveButton>
        </ButtonsContainer>
      </Form>
      
      <Modal 
        isOpen={showGenerator} 
        onClose={() => setShowGenerator(false)}
        title="Password Generator"
      >
        <PasswordGenerator onSelect={handleSelectPassword} />
      </Modal>
    </FormContainer>
  );
};

export default PasswordForm;
