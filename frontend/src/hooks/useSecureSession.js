import { useEffect } from 'react';
import { vaultService } from '../services/vaultService';

export function useSecureSession() {
  useEffect(() => {
    // Clear sensitive data on tab/window close
    const handleBeforeUnload = () => {
      vaultService.clearKeys();
    };
    
    // Clear keys on session expiration
    const handleSessionExpired = () => {
      // Show notification to user
      alert('Your session has expired for security reasons. Please log in again.');
      // Redirect to login
      window.location.href = '/login';
    };
    
    // Add event listeners
    window.addEventListener('beforeunload', handleBeforeUnload);
    window.addEventListener('vault:session-expired', handleSessionExpired);
    
    // Set initial session timeout
    vaultService.initSessionTimeout();
    
    // Reset session timeout on user activity
    const activityEvents = ['mousedown', 'keydown', 'touchstart', 'scroll'];
    const resetTimeout = () => vaultService.resetSessionTimeout();
    
    activityEvents.forEach(event => {
      document.addEventListener(event, resetTimeout);
    });
    
    // Clean up
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      window.removeEventListener('vault:session-expired', handleSessionExpired);
      
      activityEvents.forEach(event => {
        document.removeEventListener(event, resetTimeout);
      });
    };
  }, []);
}
