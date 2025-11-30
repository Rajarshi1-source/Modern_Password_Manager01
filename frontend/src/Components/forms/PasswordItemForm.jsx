import React, { useState } from 'react';
import styled from 'styled-components';
import { Formik, Form, Field, ErrorMessage } from 'formik';
import * as Yup from 'yup';
import { FaEye, FaEyeSlash, FaKey, FaRandom } from 'react-icons/fa';
import PasswordGenerator from '../PasswordGenerator';

const FormContainer = styled.div`
  max-width: 500px;
  width: 100%;
`;

const FieldGroup = styled.div`
  margin-bottom: 20px;
`;

const Label = styled.label`
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 500;
`;

const Input = styled(Field)`
  width: 100%;
  padding: 12px;
  border-radius: 4px;
  border: 1px solid ${props => props.theme.borderColor};
  background: ${props => props.theme.inputBg};
  color: ${props => props.theme.textPrimary};
  font-size: 14px;
  
  &:focus {
    outline: none;
    border-color: ${props => props.theme.primary};
  }
`;

const Textarea = styled(Input).attrs({ as: 'textarea' })`
  min-height: 120px;
  resize: vertical;
`;

const ErrorText = styled.div`
  color: ${props => props.theme.error};
  font-size: 12px;
  margin-top: 4px;
`;

const PasswordContainer = styled.div`
  position: relative;
`;

const PasswordButton = styled.button`
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: ${props => props.theme.textSecondary};
  cursor: pointer;
  
  &:hover {
    color: ${props => props.theme.primary};
  }
`;

const GeneratePasswordButton = styled.button`
  display: flex;
  align-items: center;
  gap: 8px;
  background: none;
  border: 1px solid ${props => props.theme.borderColor};
  color: ${props => props.theme.textSecondary};
  padding: 8px 16px;
  border-radius: 4px;
  font-size: 14px;
  margin-top: 8px;
  cursor: pointer;
  
  &:hover {
    background: ${props => props.theme.bgHover};
    color: ${props => props.theme.primary};
  }
`;

const SubmitButton = styled.button`
  width: 100%;
  padding: 12px;
  background: ${props => props.theme.primary};
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  
  &:hover {
    background: ${props => props.theme.primaryDark};
  }
  
  &:disabled {
    background: ${props => props.theme.textSecondary};
    cursor: not-allowed;
  }
`;

const Modal = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
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
            <FieldGroup>
              <Label htmlFor="name">Name</Label>
              <Input name="name" type="text" placeholder="e.g., Google Account" />
              <ErrorMessage name="name" component={ErrorText} />
            </FieldGroup>
            
            <FieldGroup>
              <Label htmlFor="url">Website URL</Label>
              <Input name="url" type="text" placeholder="https://example.com" />
              <ErrorMessage name="url" component={ErrorText} />
            </FieldGroup>
            
            <FieldGroup>
              <Label htmlFor="username">Username</Label>
              <Input name="username" type="text" placeholder="Your username" />
              <ErrorMessage name="username" component={ErrorText} />
            </FieldGroup>
            
            <FieldGroup>
              <Label htmlFor="email">Email</Label>
              <Input name="email" type="email" placeholder="email@example.com" />
              <ErrorMessage name="email" component={ErrorText} />
            </FieldGroup>
            
            <FieldGroup>
              <Label htmlFor="password">Password</Label>
              <PasswordContainer>
                <Input 
                  name="password" 
                  type={showPassword ? "text" : "password"} 
                  placeholder="Your secure password" 
                />
                <PasswordButton 
                  type="button" 
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? <FaEyeSlash /> : <FaEye />}
                </PasswordButton>
              </PasswordContainer>
              <ErrorMessage name="password" component={ErrorText} />
              
              <GeneratePasswordButton 
                type="button"
                onClick={() => setShowGenerator(true)}
              >
                <FaRandom /> Generate Strong Password
              </GeneratePasswordButton>
            </FieldGroup>
            
            <FieldGroup>
              <Label htmlFor="notes">Notes</Label>
              <Textarea name="notes" placeholder="Additional information..." />
              <ErrorMessage name="notes" component={ErrorText} />
            </FieldGroup>
            
            <SubmitButton type="submit" disabled={formikProps.isSubmitting}>
              {initialValues.id ? 'Update Password' : 'Save Password'}
            </SubmitButton>
            
            {showGenerator && (
              <Modal onClick={() => setShowGenerator(false)}>
                <div onClick={e => e.stopPropagation()}>
                  <PasswordGenerator 
                    onSelectPassword={(password) => handlePasswordSelect(password, formikProps)} 
                  />
                </div>
              </Modal>
            )}
          </Form>
        )}
      </Formik>
    </FormContainer>
  );
};

export default PasswordItemForm;
