import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'react-hot-toast';

const NotificationSettings = () => {
  const [settings, setSettings] = useState({
    email_alerts: true,
    sms_alerts: false,
    push_alerts: true,
    auto_lock_accounts: true,
    suspicious_activity_threshold: 3,
    alert_cooldown_minutes: 15,
    phone_number: ''
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  
  // Fetch current notification settings
  useEffect(() => {
    const fetchSettings = async () => {
      setLoading(true);
      try {
        const response = await axios.get('/api/security/account-protection/notification-settings/', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
          }
        });
        setSettings(response.data);
      } catch (error) {
        toast.error('Failed to fetch notification settings');
        console.error('Error fetching settings:', error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchSettings();
  }, []);
  
  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    
    try {
      await axios.put('/api/security/account-protection/notification-settings/', settings, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
        }
      });
      
      toast.success('Notification settings updated successfully');
    } catch (error) {
      toast.error('Failed to update notification settings');
      console.error('Error saving settings:', error);
    } finally {
      setSaving(false);
    }
  };
  
  // Handle input changes
  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setSettings({
      ...settings,
      [name]: type === 'checkbox' ? checked : value
    });
  };
  
  if (loading) {
    return (
      <div className="flex justify-center items-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }
  
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium text-gray-900">Security Notification Settings</h3>
        <p className="mt-1 text-sm text-gray-600">
          Configure how you want to be notified when suspicious login attempts are detected.
        </p>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <p className="text-sm text-blue-700">
              Configure how you want to be notified when suspicious activity is detected on your accounts.
            </p>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Alert Methods */}
        <div className="space-y-4">
          <h4 className="text-base font-medium text-gray-900">Alert Methods</h4>
          
          <div className="space-y-3">
            <div className="flex items-center">
              <input
                id="email_alerts"
                name="email_alerts"
                type="checkbox"
                checked={settings.email_alerts}
                onChange={handleChange}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <label htmlFor="email_alerts" className="ml-3 block text-sm font-medium text-gray-700">
                Email Alerts
              </label>
            </div>
            <p className="ml-7 text-sm text-gray-500">
              Receive security alerts via email when suspicious activity is detected
            </p>

            <div className="flex items-center">
              <input
                id="sms_alerts"
                name="sms_alerts"
                type="checkbox"
                checked={settings.sms_alerts}
                onChange={handleChange}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <label htmlFor="sms_alerts" className="ml-3 block text-sm font-medium text-gray-700">
                SMS Alerts
              </label>
            </div>
            <p className="ml-7 text-sm text-gray-500">
              Receive security alerts via SMS when suspicious activity is detected
            </p>

            <div className="flex items-center">
              <input
                id="push_alerts"
                name="push_alerts"
                type="checkbox"
                checked={settings.push_alerts}
                onChange={handleChange}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <label htmlFor="push_alerts" className="ml-3 block text-sm font-medium text-gray-700">
                Push Notifications
              </label>
            </div>
            <p className="ml-7 text-sm text-gray-500">
              Receive push notifications in your browser
            </p>
          </div>
        </div>

        {/* Phone Number */}
        {settings.sms_alerts && (
          <div>
            <label htmlFor="phone_number" className="block text-sm font-medium text-gray-700">
              Phone Number
            </label>
            <div className="mt-1">
              <input
                type="tel"
                id="phone_number"
                name="phone_number"
                value={settings.phone_number}
                onChange={handleChange}
                placeholder="+1234567890"
                required={settings.sms_alerts}
                className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              />
            </div>
            <p className="mt-1 text-sm text-gray-500">
              Enter your phone number in international format (e.g., +1234567890)
            </p>
          </div>
        )}

        {/* Auto-Lock Settings */}
        <div className="space-y-4">
          <h4 className="text-base font-medium text-gray-900">Automatic Protection</h4>
          
          <div className="flex items-center">
            <input
              id="auto_lock_accounts"
              name="auto_lock_accounts"
              type="checkbox"
              checked={settings.auto_lock_accounts}
              onChange={handleChange}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <label htmlFor="auto_lock_accounts" className="ml-3 block text-sm font-medium text-gray-700">
              Automatically lock social media accounts when suspicious activity is detected
            </label>
          </div>
        </div>

        {/* Threshold Settings */}
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          <div>
            <label htmlFor="suspicious_activity_threshold" className="block text-sm font-medium text-gray-700">
              Suspicious Activity Threshold
            </label>
            <div className="mt-1">
              <select
                id="suspicious_activity_threshold"
                name="suspicious_activity_threshold"
                value={settings.suspicious_activity_threshold}
                onChange={handleChange}
                className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              >
                <option value={1}>1 failed attempt</option>
                <option value={3}>3 failed attempts</option>
                <option value={5}>5 failed attempts</option>
                <option value={10}>10 failed attempts</option>
              </select>
            </div>
            <p className="mt-1 text-sm text-gray-500">
              Number of failed attempts before triggering an alert
            </p>
          </div>

          <div>
            <label htmlFor="alert_cooldown_minutes" className="block text-sm font-medium text-gray-700">
              Alert Cooldown Period
            </label>
            <div className="mt-1">
              <select
                id="alert_cooldown_minutes"
                name="alert_cooldown_minutes"
                value={settings.alert_cooldown_minutes}
                onChange={handleChange}
                className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              >
                <option value={5}>5 minutes</option>
                <option value={15}>15 minutes</option>
                <option value={30}>30 minutes</option>
                <option value={60}>1 hour</option>
              </select>
            </div>
            <p className="mt-1 text-sm text-gray-500">
              Minimum time between consecutive alerts
            </p>
          </div>
        </div>

        {/* Submit Button */}
        <div className="pt-4">
          <button 
            type="submit" 
            disabled={saving}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default NotificationSettings; 