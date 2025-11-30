/**
 * Behavioral Recovery Hook
 * 
 * Convenient hook for accessing behavioral recovery functionality
 */

import { useBehavioral } from '../contexts/BehavioralContext';

export function useBehavioralRecovery() {
  const behavioral = useBehavioral();
  
  const {
    isCapturing,
    profileStats,
    commitmentStatus,
    createBehavioralCommitments,
    getProfileStats,
    exportProfile,
    clearProfile
  } = behavioral;
  
  // Calculate profile completeness (0-100%)
  const getProfileCompleteness = () => {
    if (!profileStats) return 0;
    
    const targetSamples = 100; // Minimum samples for good profile
    const completeness = Math.min(100, (profileStats.samplesCollected / targetSamples) * 100);
    
    return Math.round(completeness);
  };
  
  // Get profile age in days
  const getProfileAge = () => {
    if (!profileStats || !profileStats.profileAge) return 0;
    return profileStats.profileAge;
  };
  
  // Check if profile is ready for commitments
  const isProfileReady = () => {
    if (!profileStats) return false;
    return profileStats.isReady && profileStats.qualityScore >= 0.7;
  };
  
  // Get recovery readiness status
  const getRecoveryReadiness = () => {
    if (commitmentStatus.ready_for_recovery) {
      return { status: 'ready', message: 'Behavioral recovery is set up and ready' };
    }
    
    if (isProfileReady()) {
      return { status: 'can_setup', message: 'Profile ready - click to set up recovery' };
    }
    
    const completeness = getProfileCompleteness();
    const daysNeeded = Math.ceil((100 - completeness) / 3.33); // ~3.33% per day
    
    return {
      status: 'building',
      message: `Building profile: ${completeness}% (${daysNeeded} days remaining)`,
      completeness,
      daysNeeded
    };
  };
  
  return {
    // State
    isCapturing,
    profileStats,
    commitmentStatus,
    
    // Computed values
    profileCompleteness: getProfileCompleteness(),
    profileAge: getProfileAge(),
    isProfileReady: isProfileReady(),
    recoveryReadiness: getRecoveryReadiness(),
    
    // Actions
    createCommitments: createBehavioralCommitments,
    getStats: getProfileStats,
    exportProfile,
    clearProfile
  };
}

