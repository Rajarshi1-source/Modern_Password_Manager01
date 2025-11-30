import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'react-hot-toast';

const VerifyIdentity = () => {
  const { socialAccountId } = useParams();
  const navigate = useNavigate();
  const [verificationCode, setVerificationCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [accountDetails, setAccountDetails] = useState(null);
  const [codeRequested, setCodeRequested] = useState(false);
  const [countdown, setCountdown] = useState(0);

  useEffect(() => {
    // Fetch account details
    const fetchAccountDetails = async () => {
      try {
        const response = await axios.get(`/api/social-accounts/${socialAccountId}/`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
          }
        });
        setAccountDetails(response.data);
      } catch (error) {
        toast.error('Failed to fetch account details');
        console.error('Error fetching account:', error);
      }
    };

    if (socialAccountId) {
      fetchAccountDetails();
    }
  }, [socialAccountId]);

  // Countdown timer for verification code
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  // Request verification code
  const handleRequestCode = async () => {
    setLoading(true);
    try {
      await axios.post(`/api/social-accounts/${socialAccountId}/request_verification/`, {}, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
        }
      });
      
      toast.success('Verification code sent to your email and phone');
      setCodeRequested(true);
      setCountdown(60); // 60-second countdown before requesting a new code
    } catch (error) {
      toast.error('Failed to send verification code');
      console.error('Error requesting code:', error);
    } finally {
      setLoading(false);
    }
  };

  // Verify identity and unlock account
  const handleVerify = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const response = await axios.post(
        `/api/social-accounts/${socialAccountId}/unlock_account/`,
        { verification_code: verificationCode },
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
          }
        }
      );
      
      if (response.data.account_unlocked) {
        toast.success('Account successfully unlocked');
        navigate('/security/account-protection');
      } else {
        toast.error('Verification failed');
      }
    } catch (error) {
      toast.error('Identity verification failed');
      console.error('Verification error:', error);
    } finally {
      setLoading(false);
    }
  };

  if (!accountDetails) {
    return (
      <div className="flex justify-center items-center py-8">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto mt-8 p-6 bg-white rounded-lg shadow-lg">
      <div className="mb-6">
        <div className="flex items-center mb-4">
          <div className="bg-orange-100 p-2 rounded-full mr-3">
            <svg className="w-6 h-6 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <h3 className="text-xl font-semibold text-gray-900">Account Locked - Verify Your Identity</h3>
        </div>
        
        <div className="bg-blue-50 border-l-4 border-blue-400 p-4 mb-6">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm text-blue-700">
                Your {accountDetails.platform} account has been locked due to suspicious activity:
              </p>
              <p className="text-sm font-medium text-blue-800 mt-1">
                {accountDetails.lock_reason || 'Unauthorized access attempt'}
              </p>
              <p className="text-sm text-blue-700 mt-1">
                Please verify your identity to unlock your account.
              </p>
            </div>
          </div>
        </div>
        
        {!codeRequested ? (
          <div className="text-center mb-6">
            <p className="text-gray-600 mb-4">
              We'll send a verification code to your registered email and phone.
            </p>
            <button 
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-4 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
              onClick={handleRequestCode}
              disabled={loading}
            >
              {loading ? 'Sending...' : 'Send Verification Code'}
            </button>
          </div>
        ) : (
          <form onSubmit={handleVerify}>
            <div className="mb-4">
              <label htmlFor="verificationCode" className="block text-sm font-medium text-gray-700 mb-2">
                Enter Verification Code
              </label>
              <input
                type="text"
                id="verificationCode"
                className="w-full px-3 py-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-lg text-center"
                value={verificationCode}
                onChange={(e) => setVerificationCode(e.target.value)}
                placeholder="Enter the 6-digit code"
                maxLength={6}
                required
              />
            </div>
            
            <div className="text-center">
              <button 
                type="submit" 
                className="w-full bg-green-600 hover:bg-green-700 text-white font-medium py-3 px-4 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 disabled:opacity-50 mb-4"
                disabled={loading || !verificationCode}
              >
                {loading ? 'Verifying...' : 'Verify and Unlock Account'}
              </button>
              
              {countdown > 0 ? (
                <p className="text-sm text-gray-500">
                  Request new code in {countdown} seconds
                </p>
              ) : (
                <button
                  type="button"
                  className="text-sm text-blue-600 hover:text-blue-500"
                  onClick={handleRequestCode}
                  disabled={loading}
                >
                  Request New Code
                </button>
              )}
            </div>
          </form>
        )}
      </div>
      
      <div className="border-t pt-4">
        <div className="text-center">
          <button
            className="text-sm text-gray-500 hover:text-gray-700"
            onClick={() => navigate('/security/account-protection')}
          >
            Back to Account Protection
          </button>
        </div>
      </div>
    </div>
  );
};

export default VerifyIdentity; 