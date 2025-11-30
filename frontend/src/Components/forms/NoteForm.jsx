import React from 'react';
import styled from 'styled-components';
import { useFormik } from 'formik';
import * as Yup from 'yup';
import { FaArrowLeft, FaSave, FaTrash, FaLock } from 'react-icons/fa';
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

const TextArea = styled.textarea`
  padding: 12px;
  font-family: inherit;
  font-size: 14px;
  border: 1px solid ${props => props.error ? props.theme.danger : props.theme.borderColor};
  border-radius: 6px;
  background: ${props => props.theme.inputBg};
  color: ${props => props.theme.textPrimary};
  min-height: 200px;
  resize: vertical;
  
  &:focus {
    outline: none;
    border-color: ${props => props.theme.accent};
    box-shadow: 0 0 0 2px ${props => props.theme.accentLight};
  }
`;

const ButtonsContainer = styled.div`
  display: flex;
  justify-content: space-between;
  margin-top: 20px;
`;

const ErrorMessage = styled.div`
  color: ${props => props.theme.danger};
  font-size: 12px;
  margin-top: 4px;
`;

/**
 * Form for creating and editing secure notes
 * @param {Object} props - Component props
 * @param {Object} [props.initialData={}] - Initial data for editing
 * @param {Function} props.onSubmit - Submit handler
 * @param {Function} props.onDelete - Delete handler
 * @param {Function} props.onCancel - Cancel handler
 */
const NoteForm = ({ 
  initialData = {},
  onSubmit,
  onDelete,
  onCancel
}) => {
  // Form validation schema
  const validationSchema = Yup.object({
    name: Yup.string().required('Title is required'),
    note: Yup.string().required('Note content is required')
  });
  
  // Initialize form
  const formik = useFormik({
    initialValues: {
      name: initialData.name || '',
      note: initialData.note || '',
      category: initialData.category || ''
    },
    validationSchema,
    onSubmit: (values) => {
      onSubmit({
        ...initialData,
        type: 'note',
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
        <Title>{initialData.id ? 'Edit Secure Note' : 'Add Secure Note'}</Title>
      </FormHeader>
      
      <Form onSubmit={formik.handleSubmit}>
        <Input
          id="name"
          name="name"
          label="Title"
          placeholder="Enter note title"
          value={formik.values.name}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          error={formik.touched.name && Boolean(formik.errors.name)}
          errorMessage={formik.touched.name && formik.errors.name}
          leftIcon={<FaLock />}
          required
        />
        
        <Input
          id="category"
          name="category"
          label="Category (optional)"
          placeholder="e.g., Personal, Work, Financial"
          value={formik.values.category}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
        />
        
        <div>
          <label htmlFor="note" style={{ 
            display: 'block', 
            marginBottom: '6px',
            fontSize: '14px',
            fontWeight: '500'
          }}>
            Note Content
          </label>
          <TextArea
            id="note"
            name="note"
            placeholder="Type your secure note here..."
            value={formik.values.note}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={formik.touched.note && Boolean(formik.errors.note)}
          />
          {formik.touched.note && formik.errors.note && (
            <ErrorMessage>{formik.errors.note}</ErrorMessage>
          )}
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
            Save Note
          </Button>
        </ButtonsContainer>
      </Form>
    </FormContainer>
  );
};

export default NoteForm;
