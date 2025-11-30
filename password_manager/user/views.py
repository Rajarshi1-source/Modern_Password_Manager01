from django.shortcuts import render, get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q
from .models import EmergencyContact, EmergencyAccessRequest
from vault.models.vault_models import EncryptedVaultItem
from vault.serializer import VaultItemSerializer
import uuid
import json
from django.core.mail import send_mail
from django.conf import settings
from password_manager.api_utils import error_response, success_response

# Create your views here.

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def profile(request):
    """
    Get or update user profile information
    """
    if request.method == 'GET':
        # Return user profile data
        user = request.user
        profile_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'date_joined': user.date_joined,
        }
        return success_response(profile_data)
    
    elif request.method == 'PUT':
        # Update user profile
        user = request.user
        data = request.data
        
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'email' in data:
            user.email = data['email']
            
        user.save()
        
        return success_response({'message': 'Profile updated successfully'})

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def emergency_access(request):
    """
    Manage emergency access settings
    """
    if request.method == 'GET':
        # Placeholder - implement actual emergency access retrieval
        return success_response({
            'emergency_contacts': [],
            'emergency_access_enabled': False,
            'waiting_period_days': 7
        })
    
    elif request.method == 'POST':
        # Placeholder - implement actual emergency access settings update
        # This would typically involve adding trusted contacts, setting
        # emergency access waiting periods, etc.
        action = request.data.get('action', '')
        
        if action == 'add_contact':
            # Add emergency contact logic
            return success_response({'message': 'Emergency contact added'})
        
        elif action == 'remove_contact':
            # Remove emergency contact logic
            return success_response({'message': 'Emergency contact removed'})
        
        elif action == 'update_settings':
            # Update settings logic
            return success_response({'message': 'Emergency access settings updated'})
        
        return error_response('Invalid action', status_code=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def preferences(request):
    """
    Get or update user preferences
    """
    from .models import UserPreferences
    
    # Get or create preferences for user
    prefs, created = UserPreferences.objects.get_or_create(user=request.user)
    
    if request.method == 'GET':
        # Return preferences as dictionary
        return success_response({
            'preferences': prefs.to_dict()
        })
    
    elif request.method == 'PUT':
        # Update preferences from request data
        data = request.data.get('preferences', {})
        
        # Update theme preferences
        theme = data.get('theme', {})
        if 'mode' in theme:
            prefs.theme_mode = theme['mode']
        if 'primaryColor' in theme:
            prefs.theme_primary_color = theme['primaryColor']
        if 'fontSize' in theme:
            prefs.theme_font_size = theme['fontSize']
        if 'fontFamily' in theme:
            prefs.theme_font_family = theme['fontFamily']
        if 'compactMode' in theme:
            prefs.theme_compact_mode = theme['compactMode']
        if 'animations' in theme:
            prefs.theme_animations = theme['animations']
        if 'highContrast' in theme:
            prefs.theme_high_contrast = theme['highContrast']
        
        # Update notification preferences
        notifications = data.get('notifications', {})
        if 'enabled' in notifications:
            prefs.notifications_enabled = notifications['enabled']
        if 'browser' in notifications:
            prefs.notifications_browser = notifications['browser']
        if 'email' in notifications:
            prefs.notifications_email = notifications['email']
        if 'push' in notifications:
            prefs.notifications_push = notifications['push']
        if 'breachAlerts' in notifications:
            prefs.notifications_breach_alerts = notifications['breachAlerts']
        if 'securityAlerts' in notifications:
            prefs.notifications_security_alerts = notifications['securityAlerts']
        if 'accountActivity' in notifications:
            prefs.notifications_account_activity = notifications['accountActivity']
        if 'marketingEmails' in notifications:
            prefs.notifications_marketing = notifications['marketingEmails']
        if 'productUpdates' in notifications:
            prefs.notifications_product_updates = notifications['productUpdates']
        if 'quietHoursEnabled' in notifications:
            prefs.notifications_quiet_hours_enabled = notifications['quietHoursEnabled']
        if 'sound' in notifications:
            prefs.notifications_sound = notifications['sound']
        if 'soundVolume' in notifications:
            prefs.notifications_sound_volume = notifications['soundVolume']
        
        # Update security preferences
        security = data.get('security', {})
        if 'autoLockEnabled' in security:
            prefs.security_auto_lock_enabled = security['autoLockEnabled']
        if 'autoLockTimeout' in security:
            prefs.security_auto_lock_timeout = security['autoLockTimeout']
        if 'biometricAuth' in security:
            prefs.security_biometric_auth = security['biometricAuth']
        if 'twoFactorAuth' in security:
            prefs.security_two_factor_auth = security['twoFactorAuth']
        if 'clearClipboard' in security:
            prefs.security_clear_clipboard = security['clearClipboard']
        if 'clipboardTimeout' in security:
            prefs.security_clipboard_timeout = security['clipboardTimeout']
        if 'defaultPasswordLength' in security:
            prefs.security_default_password_length = security['defaultPasswordLength']
        if 'breachMonitoring' in security:
            prefs.security_breach_monitoring = security['breachMonitoring']
        if 'darkWebMonitoring' in security:
            prefs.security_dark_web_monitoring = security['darkWebMonitoring']
        
        # Update privacy preferences
        privacy = data.get('privacy', {})
        if 'analytics' in privacy:
            prefs.privacy_analytics = privacy['analytics']
        if 'errorReporting' in privacy:
            prefs.privacy_error_reporting = privacy['errorReporting']
        if 'performanceMonitoring' in privacy:
            prefs.privacy_performance_monitoring = privacy['performanceMonitoring']
        
        # Update UI preferences
        ui = data.get('ui', {})
        if 'language' in ui:
            prefs.ui_language = ui['language']
        if 'dateFormat' in ui:
            prefs.ui_date_format = ui['dateFormat']
        if 'timeFormat' in ui:
            prefs.ui_time_format = ui['timeFormat']
        if 'vaultView' in ui:
            prefs.ui_vault_view = ui['vaultView']
        if 'sortBy' in ui:
            prefs.ui_sort_by = ui['sortBy']
        if 'sortOrder' in ui:
            prefs.ui_sort_order = ui['sortOrder']
        if 'sidebarCollapsed' in ui:
            prefs.ui_sidebar_collapsed = ui['sidebarCollapsed']
        
        # Update accessibility preferences
        accessibility = data.get('accessibility', {})
        if 'reducedMotion' in accessibility:
            prefs.accessibility_reduced_motion = accessibility['reducedMotion']
        if 'largeText' in accessibility:
            prefs.accessibility_large_text = accessibility['largeText']
        
        # Update advanced preferences
        advanced = data.get('advanced', {})
        if 'developerMode' in advanced:
            prefs.advanced_developer_mode = advanced['developerMode']
        if 'experimentalFeatures' in advanced:
            prefs.advanced_experimental_features = advanced['experimentalFeatures']
        if 'autoSync' in advanced:
            prefs.advanced_auto_sync = advanced['autoSync']
        if 'syncInterval' in advanced:
            prefs.advanced_sync_interval = advanced['syncInterval']
        
        # Save preferences
        prefs.last_synced = timezone.now()
        prefs.save()
        
        return success_response({
            'message': 'Preferences updated successfully',
            'preferences': prefs.to_dict()
        })

@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def emergency_contacts(request):
    """
    Manage emergency contacts for a user
    GET: Retrieve all emergency contacts
    POST: Add a new emergency contact
    """
    user = request.user
    
    if request.method == 'GET':
        # Retrieve contacts where I am the vault owner
        my_contacts = EmergencyContact.objects.filter(vault_owner=user)
        
        # Retrieve contacts where I am an emergency contact
        trusted_for = EmergencyContact.objects.filter(emergency_contact=user)
        
        contacts_data = {
            'my_emergency_contacts': [
                {
                    'id': contact.id,
                    'email': contact.email,
                    'username': contact.emergency_contact.username,
                    'access_type': contact.access_type,
                    'waiting_period_hours': contact.waiting_period_hours,
                    'status': contact.status,
                    'created_at': contact.created_at
                } for contact in my_contacts
            ],
            'i_am_trusted_for': [
                {
                    'id': contact.id,
                    'username': contact.vault_owner.username,
                    'access_type': contact.access_type,
                    'waiting_period_hours': contact.waiting_period_hours,
                    'status': contact.status,
                    'created_at': contact.created_at
                } for contact in trusted_for
            ]
        }
        
        return success_response(contacts_data)
        
    elif request.method == 'POST':
        # Add a new emergency contact
        email = request.data.get('email')
        waiting_period = request.data.get('waiting_period_hours', 24)
        access_type = request.data.get('access_type', 'view')
        
        if not email:
            return error_response('Email is required', status_code=status.HTTP_400_BAD_REQUEST)
            
        try:
            contact_user = User.objects.get(email=email)
            
            # Prevent adding yourself
            if contact_user.id == user.id:
                return error_response('You cannot add yourself as an emergency contact', 
                               status_code=status.HTTP_400_BAD_REQUEST)
                
            # Check if already exists
            if EmergencyContact.objects.filter(vault_owner=user, emergency_contact=contact_user).exists():
                return error_response('This user is already an emergency contact', 
                               status_code=status.HTTP_400_BAD_REQUEST)
                
            # Create emergency contact
            contact = EmergencyContact.objects.create(
                vault_owner=user,
                emergency_contact=contact_user,
                email=email,
                waiting_period_hours=waiting_period,
                access_type=access_type,
                status='pending'
            )
            
            # Send notification email to the emergency contact
            send_mail(
                'Emergency Access Invitation',
                f'{user.username} has designated you as their emergency contact for their password vault. '
                f'Please log in to approve or reject this request.',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=True,
            )
            
            return success_response({
                'id': contact.id,
                'email': email,
                'username': contact_user.username,
                'status': 'pending',
                'waiting_period_hours': waiting_period,
                'access_type': access_type
            }, status_code=status.HTTP_201_CREATED)
            
        except User.DoesNotExist:
            # User not found, but we'll create a placeholder
            return error_response('User not found with this email', 
                           status_code=status.HTTP_404_NOT_FOUND)
    
    elif request.method == 'DELETE':
        contact_id = request.data.get('contact_id')
        
        if not contact_id:
            return error_response('Contact ID is required', 
                           status_code=status.HTTP_400_BAD_REQUEST)
                           
        contact = get_object_or_404(EmergencyContact, id=contact_id, vault_owner=user)
        contact.delete()
        
        return success_response({'message': 'Emergency contact removed'})

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def emergency_contact_update(request, contact_id):
    """Update emergency contact settings"""
    user = request.user
    
    contact = get_object_or_404(EmergencyContact, id=contact_id, vault_owner=user)
    
    # Fields that can be updated
    if 'waiting_period_hours' in request.data:
        contact.waiting_period_hours = request.data['waiting_period_hours']
        
    if 'access_type' in request.data:
        contact.access_type = request.data['access_type']
        
    contact.save()
    
    return success_response({
        'id': contact.id,
        'email': contact.email,
        'username': contact.emergency_contact.username,
        'waiting_period_hours': contact.waiting_period_hours,
        'access_type': contact.access_type,
        'status': contact.status
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def respond_to_invitation(request):
    """Respond to an emergency contact invitation"""
    user = request.user
    contact_id = request.data.get('contact_id')
    response = request.data.get('response', 'rejected')  # Default is reject
    
    if not contact_id:
        return error_response('Contact ID is required', 
                       status_code=status.HTTP_400_BAD_REQUEST)
                       
    contact = get_object_or_404(EmergencyContact, id=contact_id, emergency_contact=user)
    
    # Update status based on response
    if response == 'approved':
        contact.status = 'approved'
    else:
        contact.status = 'rejected'
        
    contact.save()
    
    # Notify the vault owner
    send_mail(
        f'Emergency Contact {contact.status.title()}',
        f'{user.username} has {contact.status} your emergency contact request.',
        settings.DEFAULT_FROM_EMAIL,
        [contact.vault_owner.email],
        fail_silently=True,
    )
    
    return success_response({'status': contact.status})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_emergency_access(request):
    """Request emergency access to a vault"""
    user = request.user
    contact_id = request.data.get('contact_id')
    reason = request.data.get('reason', '')
    
    if not contact_id:
        return error_response('Contact ID is required', 
                       status_code=status.HTTP_400_BAD_REQUEST)
                       
    contact = get_object_or_404(EmergencyContact, id=contact_id, emergency_contact=user, status='approved')
    
    # Check if there's already an active request
    active_request = EmergencyAccessRequest.objects.filter(
        emergency_contact=contact, 
        status__in=['pending', 'approved', 'auto_approved']
    ).first()
    
    if active_request:
        return error_response('You already have an active request', 
            status_code=status.HTTP_400_BAD_REQUEST,
            details={
                'request_id': active_request.id,
                'status': active_request.status,
                'auto_approve_at': active_request.auto_approve_at
            })
        
    # Create access request
    access_request = EmergencyAccessRequest.objects.create(
        emergency_contact=contact,
        reason=reason,
        access_key=str(uuid.uuid4())
    )
    
    # Auto-calculate the approval time
    auto_approve_at = timezone.now() + timezone.timedelta(hours=contact.waiting_period_hours)
    
    # Notify the vault owner
    send_mail(
        'Emergency Access Request',
        f'{user.username} has requested emergency access to your vault. '
        f'If you do not respond, access will be granted automatically after the waiting period '
        f'({contact.waiting_period_hours} hours).',
        settings.DEFAULT_FROM_EMAIL,
        [contact.vault_owner.email],
        fail_silently=True,
    )
    
    return success_response({
        'request_id': access_request.id,
        'status': 'pending',
        'auto_approve_at': auto_approve_at,
        'access_type': contact.access_type
    }, status_code=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def respond_to_access_request(request):
    """Approve or reject an emergency access request"""
    user = request.user
    request_id = request.data.get('request_id')
    response = request.data.get('response', 'rejected')  # Default is reject
    
    if not request_id:
        return error_response('Request ID is required', 
                       status_code=status.HTTP_400_BAD_REQUEST)
                       
    access_request = get_object_or_404(EmergencyAccessRequest, id=request_id, emergency_contact__vault_owner=user)
    
    # Update status based on response
    if response == 'approved':
        access_request.status = 'approved'
        access_request.approved_at = timezone.now()
        
        # Set expiration for access (default 24 hours from approval)
        access_request.expires_at = timezone.now() + timezone.timedelta(hours=24)
        access_request.access_granted_at = timezone.now()
    else:
        access_request.status = 'rejected'
        access_request.rejected_at = timezone.now()
        
    access_request.save()
    
    # Notify the requestor
    send_mail(
        f'Emergency Access Request {access_request.status.title()}',
        f'Your request for emergency access to {user.username}\'s vault has been {access_request.status}.',
        settings.DEFAULT_FROM_EMAIL,
        [access_request.emergency_contact.emergency_contact.email],
        fail_silently=True,
    )
    
    return success_response({'status': access_request.status})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_access_requests(request):
    """Check status of emergency access requests"""
    user = request.user
    
    # Requests I've made to access others' vaults
    my_requests = EmergencyAccessRequest.objects.filter(
        emergency_contact__emergency_contact=user
    ).select_related('emergency_contact')
    
    # Requests others have made to access my vault
    others_requests = EmergencyAccessRequest.objects.filter(
        emergency_contact__vault_owner=user
    ).select_related('emergency_contact')
    
    # Process auto-approval for pending requests
    for req in others_requests.filter(status='pending'):
        if req.auto_approve_at and timezone.now() >= req.auto_approve_at:
            req.status = 'auto_approved'
            req.access_granted_at = timezone.now()
            req.expires_at = timezone.now() + timezone.timedelta(hours=24)
            req.save()
    
    # Format response data
    my_requests_data = [
        {
            'id': req.id,
            'vault_owner': req.emergency_contact.vault_owner.username,
            'status': req.status,
            'requested_at': req.requested_at,
            'auto_approve_at': req.auto_approve_at,
            'expires_at': req.expires_at,
            'access_type': req.emergency_contact.access_type
        } for req in my_requests
    ]
    
    others_requests_data = [
        {
            'id': req.id,
            'emergency_contact': req.emergency_contact.emergency_contact.username,
            'status': req.status,
            'requested_at': req.requested_at,
            'auto_approve_at': req.auto_approve_at,
            'reason': req.reason,
            'expires_at': req.expires_at,
            'access_type': req.emergency_contact.access_type
        } for req in others_requests
    ]
    
    return success_response({
        'my_requests': my_requests_data,
        'others_requests': others_requests_data
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def access_emergency_vault(request, request_id):
    """Access a vault in emergency mode"""
    user = request.user
    
    # Get the access request
    access_request = get_object_or_404(
        EmergencyAccessRequest,
        id=request_id,
        emergency_contact__emergency_contact=user,
        status__in=['approved', 'auto_approved']
    )
    
    # Check if expired
    if access_request.expires_at and timezone.now() > access_request.expires_at:
        access_request.status = 'expired'
        access_request.save()
        return error_response('Emergency access has expired', 
                       status_code=status.HTTP_403_FORBIDDEN)
    
    # Get vault items
    vault_owner = access_request.emergency_contact.vault_owner
    vault_items = EncryptedVaultItem.objects.filter(user=vault_owner, deleted=False)
    
    # Serialize items
    serializer = VaultItemSerializer(vault_items, many=True)
    
    # For view-only access, we might want to restrict certain operations
    access_type = access_request.emergency_contact.access_type
    
    return success_response({
        'vault_owner': vault_owner.username,
        'access_type': access_type,
        'items': serializer.data,
        'expires_at': access_request.expires_at
    })
