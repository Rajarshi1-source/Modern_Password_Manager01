import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import { format } from 'date-fns';

const LoginHistory = () => {
  const [loginAttempts, setLoginAttempts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all'); // 'all', 'suspicious', 'normal'
  
  useEffect(() => {
    fetchLoginHistory();
  }, [filter, fetchLoginHistory]);
  
  const fetchLoginHistory = useCallback(async () => {
    setLoading(true);
    try {
      let url = '/api/security/account-protection/login-attempts/';
      if (filter === 'suspicious') {
        url += '?suspicious_only=true';
      }
      
      const response = await axios.get(url, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
        }
      });
      
      setLoginAttempts(response.data.attempts || []);
    } catch (error) {
      toast.error('Failed to fetch login history');
      console.error('Error fetching login history:', error);
    } finally {
      setLoading(false);
    }
  }, [filter]);
  
  // Determine the appropriate status label and class based on the login attempt
  const getStatusInfo = (attempt) => {
    if (attempt.is_suspicious) {
      return {
        label: 'Suspicious',
        className: 'bg-red-100 text-red-800 px-2 py-1 rounded-full text-xs font-medium'
      };
    }
    if (attempt.status === 'failed') {
      return {
        label: 'Failed',
        className: 'bg-yellow-100 text-yellow-800 px-2 py-1 rounded-full text-xs font-medium'
      };
    }
    return {
      label: 'Success',
      className: 'bg-green-100 text-green-800 px-2 py-1 rounded-full text-xs font-medium'
    };
  };

  const formatDate = (dateString) => {
    try {
      return format(new Date(dateString), 'MMM d, yyyy h:mm a');
    } catch (error) {
      return dateString;
    }
  };
  
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium text-gray-900">Login History</h3>
        <div className="flex space-x-2">
          <button 
            className={`px-3 py-1 rounded-md text-sm font-medium ${
              filter === 'all' 
                ? 'bg-blue-600 text-white' 
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
            onClick={() => setFilter('all')}
          >
            All
          </button>
          <button 
            className={`px-3 py-1 rounded-md text-sm font-medium ${
              filter === 'suspicious' 
                ? 'bg-red-600 text-white' 
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
            onClick={() => setFilter('suspicious')}
          >
            Suspicious Only
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center items-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      ) : loginAttempts.length === 0 ? (
        <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
          <p className="text-blue-700 text-sm">
            No login attempts found.
          </p>
        </div>
      ) : (
        <div className="bg-white shadow overflow-hidden sm:rounded-md">
          <ul className="divide-y divide-gray-200">
            {loginAttempts.map((attempt, index) => {
              const statusInfo = getStatusInfo(attempt);
              
              return (
                <li 
                  key={attempt.id || index} 
                  className={`px-6 py-4 ${attempt.is_suspicious ? 'bg-red-50' : 'hover:bg-gray-50'}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <p className="text-sm font-medium text-gray-900 truncate">
                            {formatDate(attempt.timestamp)}
                          </p>
                          <div className="mt-1 flex items-center space-x-4 text-sm text-gray-500">
                            <span>IP: {attempt.ip_address}</span>
                            {attempt.location && (
                              <span>Location: {attempt.location}</span>
                            )}
                            {attempt.user_agent && (
                              <span className="truncate max-w-xs">
                                {attempt.user_agent.split(' ')[0]}
                              </span>
                            )}
                          </div>
                          {attempt.failure_reason && (
                            <p className="mt-1 text-sm text-red-600">
                              {attempt.failure_reason}
                            </p>
                          )}
                        </div>
                        <div className="flex items-center space-x-3">
                          <span className={statusInfo.className}>
                            {statusInfo.label}
                          </span>
                          {attempt.threat_score > 0 && (
                            <span className="text-xs text-gray-500">
                              Threat Score: {attempt.threat_score}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
};

export default LoginHistory; 