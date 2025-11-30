"""
MFA Integration Module
Integrates Multi-Factor Authentication with existing 2FA system
Bridges biometric authentication, adaptive MFA, and traditional 2FA (TOTP, SMS, Email)
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
import logging

from .mfa_models import BiometricFactor, MFAPolicy, AuthenticationAttempt
from .mfa_views import BiometricAuthenticator
from ..two_factor.models import TOTPDevice  # Existing 2FA model
from authy_service import AuthyService  # Existing Authy integration

User = get_user_model()
logger = logging.getLogger(__name__)


class MFAIntegrationService:
    """
    Service for integrating MFA with existing authentication systems
    """
    
    def __init__(self, user):
        self.user = user
        self.authy_service = AuthyService()
        self.biometric_auth = BiometricAuthenticator()
    
    def get_all_enabled_factors(self):
        """
        Get all enabled authentication factors (traditional 2FA + biometric MFA)
        
        Returns:
            dict: Dictionary of enabled factors by category
        """
        factors = {
            'traditional_2fa': [],
            'biometric_mfa': [],
            'all_factors': []
        }
        
        # Check traditional 2FA methods
        try:
            totp_device = TOTPDevice.objects.filter(user=self.user, confirmed=True).first()
            if totp_device:
                factors['traditional_2fa'].append('totp')
                factors['all_factors'].append('totp')
        except Exception as e:
            logger.warning(f"Error checking TOTP device: {e}")
        
        # Check SMS/Email 2FA (Authy)
        if hasattr(self.user, 'authy_id') and self.user.authy_id:
            factors['traditional_2fa'].extend(['sms', 'email'])
            factors['all_factors'].extend(['sms', 'email'])
        
        # Check biometric MFA
        biometric_factors = BiometricFactor.objects.filter(
            user=self.user,
            is_active=True
        )
        
        for bio_factor in biometric_factors:
            factors['biometric_mfa'].append(bio_factor.factor_type)
            factors['all_factors'].append(bio_factor.factor_type)
        
        return factors
    
    def assess_authentication_risk(self, request_data):
        """
        Assess risk level for current authentication attempt
        
        Args:
            request_data (dict): Request metadata (IP, device, location, etc.)
        
        Returns:
            dict: Risk assessment with required factors
        """
        from .mfa_views import AdaptiveMFAService
        
        adaptive_service = AdaptiveMFAService(self.user)
        risk_assessment = adaptive_service.assess_risk(request_data)
        
        return risk_assessment
    
    def determine_required_factors(self, request_data, operation_type='login'):
        """
        Determine which authentication factors are required based on:
        - User's MFA policy
        - Current risk level
        - Operation type (login, sensitive_action, etc.)
        
        Args:
            request_data (dict): Request metadata
            operation_type (str): Type of operation being performed
        
        Returns:
            dict: Required factors and policy information
        """
        # Get user's MFA policy
        policy = MFAPolicy.objects.filter(user=self.user).first()
        
        if not policy:
            # Default policy: require at least one 2FA method
            return {
                'required_count': 1,
                'required_factors': [],
                'allow_any': True,
                'risk_level': 'low',
                'policy_reason': 'default_policy'
            }
        
        # Assess risk
        risk_assessment = self.assess_authentication_risk(request_data)
        risk_level = risk_assessment.get('risk_level', 'low')
        
        # Determine requirements based on policy and risk
        required_factors = []
        required_count = 1
        allow_any = True
        
        if policy.adaptive_mfa_enabled:
            # Adaptive MFA: adjust based on risk
            if risk_level == 'high':
                # High risk: require biometric + traditional 2FA
                required_count = 2
                required_factors = risk_assessment.get('required_factors', [])
                allow_any = False
            elif risk_level == 'medium':
                # Medium risk: require any 2FA
                required_count = 1
                allow_any = True
            else:
                # Low risk: optional 2FA (for trusted devices)
                if policy.remember_trusted_devices and self._is_trusted_device(request_data):
                    required_count = 0
                else:
                    required_count = 1
                    allow_any = True
        
        # Override for sensitive operations
        if operation_type in ['export_vault', 'delete_account', 'change_master_password']:
            if policy.require_biometric_for_sensitive:
                required_factors = ['face', 'voice', 'totp']
                required_count = 1
                allow_any = True  # Any biometric OR TOTP
        
        # Check for new device/location requirements
        if policy.require_mfa_on_new_device and self._is_new_device(request_data):
            required_count = max(required_count, 1)
        
        if policy.require_mfa_on_new_location and self._is_new_location(request_data):
            required_count = max(required_count, 1)
        
        return {
            'required_count': required_count,
            'required_factors': required_factors,
            'allow_any': allow_any,
            'risk_level': risk_level,
            'policy_reason': f'{operation_type}_{risk_level}_risk'
        }
    
    def verify_multi_factor(self, factors_provided, request_data):
        """
        Verify multiple authentication factors
        
        Args:
            factors_provided (dict): Dictionary of factor_type -> credential
                Example: {
                    'totp': '123456',
                    'face': <image_data>,
                    'sms': '789012'
                }
            request_data (dict): Request metadata
        
        Returns:
            dict: Verification result
        """
        requirements = self.determine_required_factors(request_data)
        
        verified_factors = []
        verification_results = {}
        
        # Verify each provided factor
        for factor_type, credential in factors_provided.items():
            try:
                if factor_type == 'totp':
                    result = self._verify_totp(credential)
                elif factor_type == 'sms':
                    result = self._verify_sms(credential)
                elif factor_type == 'email':
                    result = self._verify_email(credential)
                elif factor_type in ['face', 'voice']:
                    result = self._verify_biometric(factor_type, credential)
                else:
                    result = {'success': False, 'error': f'Unknown factor type: {factor_type}'}
                
                verification_results[factor_type] = result
                
                if result.get('success'):
                    verified_factors.append(factor_type)
                    
                # Log attempt
                AuthenticationAttempt.objects.create(
                    user=self.user,
                    factor_type=factor_type,
                    success=result.get('success', False),
                    ip_address=request_data.get('ip_address'),
                    device_info=request_data.get('user_agent'),
                    location=request_data.get('location')
                )
                
            except Exception as e:
                logger.error(f"Error verifying {factor_type}: {e}")
                verification_results[factor_type] = {'success': False, 'error': str(e)}
        
        # Check if requirements are met
        success = False
        reason = ''
        
        if requirements['allow_any']:
            # User can use any available factor
            if len(verified_factors) >= requirements['required_count']:
                success = True
                reason = f"Verified {len(verified_factors)} factor(s)"
            else:
                reason = f"Required {requirements['required_count']} factor(s), got {len(verified_factors)}"
        else:
            # Specific factors required
            required_set = set(requirements['required_factors'])
            verified_set = set(verified_factors)
            
            if verified_set.intersection(required_set):
                success = True
                reason = f"Verified required factor(s)"
            else:
                reason = f"Required one of {requirements['required_factors']}, got {verified_factors}"
        
        return {
            'success': success,
            'verified_factors': verified_factors,
            'verification_results': verification_results,
            'requirements': requirements,
            'reason': reason
        }
    
    def _verify_totp(self, code):
        """Verify TOTP code using existing 2FA system"""
        try:
            totp_device = TOTPDevice.objects.filter(user=self.user, confirmed=True).first()
            if not totp_device:
                return {'success': False, 'error': 'TOTP not configured'}
            
            is_valid = totp_device.verify_token(code)
            return {'success': is_valid}
        except Exception as e:
            logger.error(f"TOTP verification error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _verify_sms(self, code):
        """Verify SMS code using Authy service"""
        try:
            result = self.authy_service.verify_token(self.user.authy_id, code)
            return {'success': result.get('success', False)}
        except Exception as e:
            logger.error(f"SMS verification error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _verify_email(self, code):
        """Verify email code using Authy service"""
        return self._verify_sms(code)  # Authy handles both SMS and email
    
    def _verify_biometric(self, factor_type, data):
        """Verify biometric factor using ML model"""
        try:
            if factor_type == 'face':
                result = self.biometric_auth.verify_face(self.user, data)
            elif factor_type == 'voice':
                result = self.biometric_auth.verify_voice(self.user, data)
            else:
                return {'success': False, 'error': f'Unsupported biometric type: {factor_type}'}
            
            return result
        except Exception as e:
            logger.error(f"Biometric verification error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _is_trusted_device(self, request_data):
        """Check if device is trusted"""
        # Implementation: check against stored trusted devices
        device_fingerprint = request_data.get('device_fingerprint')
        if not device_fingerprint:
            return False
        
        # Check last successful auth from this device within trust period
        recent_success = AuthenticationAttempt.objects.filter(
            user=self.user,
            success=True,
            device_info__contains=device_fingerprint
        ).order_by('-timestamp').first()
        
        if recent_success:
            from django.utils import timezone
            from datetime import timedelta
            trust_period = timedelta(days=30)
            return (timezone.now() - recent_success.timestamp) < trust_period
        
        return False
    
    def _is_new_device(self, request_data):
        """Check if this is a new device"""
        device_fingerprint = request_data.get('device_fingerprint')
        if not device_fingerprint:
            return True
        
        return not AuthenticationAttempt.objects.filter(
            user=self.user,
            device_info__contains=device_fingerprint,
            success=True
        ).exists()
    
    def _is_new_location(self, request_data):
        """Check if this is a new location"""
        location = request_data.get('location')
        if not location:
            return True
        
        return not AuthenticationAttempt.objects.filter(
            user=self.user,
            location__contains=location,
            success=True
        ).exists()
    
    @staticmethod
    def initiate_sms_challenge(user):
        """Initiate SMS challenge using Authy"""
        authy_service = AuthyService()
        return authy_service.send_sms(user.authy_id)
    
    @staticmethod
    def initiate_email_challenge(user):
        """Initiate email challenge using Authy"""
        authy_service = AuthyService()
        return authy_service.send_email(user.authy_id)


# Convenience function for authentication middleware
def verify_mfa_for_request(user, request):
    """
    Verify MFA for a request
    
    Args:
        user: Django User object
        request: Django HttpRequest object
    
    Returns:
        bool: Whether MFA verification succeeded
    
    Raises:
        AuthenticationFailed: If MFA is required but not provided or invalid
    """
    integration_service = MFAIntegrationService(user)
    
    # Extract request data
    request_data = {
        'ip_address': request.META.get('REMOTE_ADDR'),
        'user_agent': request.META.get('HTTP_USER_AGENT'),
        'device_fingerprint': request.META.get('HTTP_X_DEVICE_FINGERPRINT'),
        'location': request.META.get('HTTP_X_LOCATION')
    }
    
    # Determine requirements
    requirements = integration_service.determine_required_factors(request_data)
    
    # If no factors required (trusted device), allow
    if requirements['required_count'] == 0:
        return True
    
    # Extract provided factors from request
    factors_provided = {}
    
    # Check for TOTP in header
    totp_code = request.META.get('HTTP_X_TOTP_CODE')
    if totp_code:
        factors_provided['totp'] = totp_code
    
    # Check for biometric data in request body (for API calls)
    if hasattr(request, 'data'):
        if 'face_data' in request.data:
            factors_provided['face'] = request.data['face_data']
        if 'voice_data' in request.data:
            factors_provided['voice'] = request.data['voice_data']
        if 'sms_code' in request.data:
            factors_provided['sms'] = request.data['sms_code']
    
    # If no factors provided, check if MFA is required
    if not factors_provided:
        if requirements['required_count'] > 0:
            raise AuthenticationFailed({
                'error': 'MFA required',
                'requirements': requirements
            })
        return True
    
    # Verify provided factors
    result = integration_service.verify_multi_factor(factors_provided, request_data)
    
    if not result['success']:
        raise AuthenticationFailed({
            'error': 'MFA verification failed',
            'reason': result['reason'],
            'requirements': requirements
        })
    
    return True

