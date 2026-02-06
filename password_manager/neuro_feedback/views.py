"""
Neuro-Feedback API Views
========================

REST API endpoints for neuro-feedback password training:
- Device management
- Training sessions
- Memory progress tracking
- Settings management

@author Password Manager Team
@created 2026-02-07
"""

import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone

from .models import (
    EEGDevice,
    BrainwaveSession,
    PasswordTrainingProgram,
    MemoryStrengthScore,
    SpacedRepetitionSchedule,
    NeuroFeedbackSettings,
)
from .services import (
    EEGDeviceService,
    MemoryTrainingService,
)

logger = logging.getLogger(__name__)


def success_response(data, status_code=status.HTTP_200_OK):
    """Standard success response."""
    return Response({'success': True, **data}, status=status_code)


def error_response(message, status_code=status.HTTP_400_BAD_REQUEST):
    """Standard error response."""
    return Response({'success': False, 'error': message}, status=status_code)


# =============================================================================
# Device Management
# =============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def devices(request):
    """List or register EEG devices."""
    service = EEGDeviceService(request.user)
    
    if request.method == 'GET':
        devices = service.get_user_devices()
        device_data = [{
            'id': str(d.id),
            'device_type': d.device_type,
            'device_type_display': d.get_device_type_display(),
            'device_name': d.device_name,
            'status': d.status,
            'battery_level': d.battery_level,
            'signal_quality_threshold': d.signal_quality_threshold,
            'last_connected_at': d.last_connected_at.isoformat() if d.last_connected_at else None,
            'is_calibrated': bool(d.baseline_alpha),
        } for d in devices]
        
        return success_response({'devices': device_data})
    
    elif request.method == 'POST':
        data = request.data
        required = ['device_id', 'device_type', 'device_name']
        
        for field in required:
            if field not in data:
                return error_response(f"Missing required field: {field}")
        
        device = service.register_device(
            device_id=data['device_id'],
            device_type=data['device_type'],
            device_name=data['device_name'],
            firmware_version=data.get('firmware_version', ''),
        )
        
        return success_response({
            'device_id': str(device.id),
            'message': f"Device '{device.device_name}' registered successfully",
        }, status_code=status.HTTP_201_CREATED)


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def device_detail(request, device_id):
    """Get or delete a specific device."""
    try:
        device = EEGDevice.objects.get(id=device_id, user=request.user)
    except EEGDevice.DoesNotExist:
        return error_response("Device not found", status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        return success_response({
            'device': {
                'id': str(device.id),
                'device_type': device.device_type,
                'device_name': device.device_name,
                'status': device.status,
                'calibration_data': device.calibration_data,
                'baseline_alpha': device.baseline_alpha,
                'baseline_theta': device.baseline_theta,
                'battery_level': device.battery_level,
                'firmware_version': device.firmware_version,
                'last_connected_at': device.last_connected_at.isoformat() if device.last_connected_at else None,
            }
        })
    
    elif request.method == 'DELETE':
        service = EEGDeviceService(request.user)
        service.unregister_device(device_id)
        return success_response({'message': 'Device removed successfully'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calibrate_device(request, device_id):
    """Initiate device calibration."""
    try:
        device = EEGDevice.objects.get(id=device_id, user=request.user)
    except EEGDevice.DoesNotExist:
        return error_response("Device not found", status.HTTP_404_NOT_FOUND)
    
    # Note: Actual calibration happens via WebSocket for real-time feedback
    # This endpoint starts the calibration process
    device.status = 'calibrating'
    device.save()
    
    return success_response({
        'message': 'Calibration started. Connect via WebSocket for real-time updates.',
        'calibration_id': str(device.id),
    })


# =============================================================================
# Training Programs
# =============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def training_programs(request):
    """List or create training programs."""
    service = MemoryTrainingService(request.user)
    
    if request.method == 'GET':
        programs = service.get_active_programs()
        program_data = [service.get_program_progress(p) for p in programs]
        
        return success_response({'programs': program_data})
    
    elif request.method == 'POST':
        data = request.data
        
        if 'vault_item_id' not in data:
            return error_response("Missing vault_item_id")
        
        if 'password' not in data:
            return error_response("Password required to create training program")
        
        try:
            from vault.models import EncryptedVaultItem
            vault_item = EncryptedVaultItem.objects.get(
                id=data['vault_item_id'],
                user=request.user
            )
        except Exception:
            return error_response("Vault item not found", status.HTTP_404_NOT_FOUND)
        
        program = service.create_training_program(vault_item, data['password'])
        progress = service.get_program_progress(program)
        
        return success_response({
            'program': progress,
            'message': f"Training program created for {program.chunk_count} chunks",
        }, status_code=status.HTTP_201_CREATED)


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def training_program_detail(request, program_id):
    """Get or delete a training program."""
    try:
        program = PasswordTrainingProgram.objects.get(id=program_id, user=request.user)
    except PasswordTrainingProgram.DoesNotExist:
        return error_response("Program not found", status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        service = MemoryTrainingService(request.user)
        progress = service.get_program_progress(program)
        
        # Include chunk-level details
        chunks = [{
            'index': s.chunk_index,
            'strength': s.strength_score,
            'is_mastered': s.is_mastered,
            'successful_recalls': s.successful_recalls,
            'failed_recalls': s.failed_recalls,
            'last_practiced_at': s.last_practiced_at.isoformat() if s.last_practiced_at else None,
        } for s in program.memory_scores.all()]
        
        progress['chunks'] = chunks
        
        return success_response({'program': progress})
    
    elif request.method == 'DELETE':
        program.status = 'abandoned'
        program.save()
        return success_response({'message': 'Program abandoned'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_training_session(request, program_id):
    """Start a training session for a program."""
    try:
        program = PasswordTrainingProgram.objects.get(id=program_id, user=request.user)
    except PasswordTrainingProgram.DoesNotExist:
        return error_response("Program not found", status.HTTP_404_NOT_FOUND)
    
    # Get preferred device
    device_service = EEGDeviceService(request.user)
    device = device_service.get_preferred_device()
    
    if not device:
        return error_response("No EEG device available. Please pair a device first.")
    
    # Create session
    session = BrainwaveSession.objects.create(
        user=request.user,
        device=device,
        status='active',
    )
    
    return success_response({
        'session_id': str(session.id),
        'program_id': str(program.id),
        'device_name': device.device_name,
        'message': 'Training session started. Connect via WebSocket for real-time feedback.',
        'websocket_url': f'/ws/neuro-training/{session.id}/',
    })


# =============================================================================
# Memory Progress
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def memory_progress(request, program_id):
    """Get detailed memory progress for a program."""
    try:
        program = PasswordTrainingProgram.objects.get(id=program_id, user=request.user)
    except PasswordTrainingProgram.DoesNotExist:
        return error_response("Program not found", status.HTTP_404_NOT_FOUND)
    
    scores = program.memory_scores.all()
    
    # Calculate overall stats
    total_strength = sum(s.strength_score for s in scores)
    avg_strength = total_strength / len(scores) if scores else 0
    
    # Forgetting curve data
    curve_data = []
    for score in scores:
        curve_data.append({
            'chunk_index': score.chunk_index,
            'current_strength': score.strength_score,
            'peak_strength': score.peak_strength,
            'decay_rate': score.decay_rate,
            'time_since_practice': (
                (timezone.now() - score.last_practiced_at).total_seconds() / 3600
                if score.last_practiced_at else None
            ),
        })
    
    return success_response({
        'average_strength': round(avg_strength, 3),
        'mastery_progress': f"{sum(1 for s in scores if s.is_mastered)}/{len(scores)}",
        'curve_data': curve_data,
    })


# =============================================================================
# Schedule
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def review_schedule(request):
    """Get upcoming review schedule."""
    schedules = SpacedRepetitionSchedule.objects.filter(
        program__user=request.user,
        completed_at__isnull=True,
        skipped=False,
    ).select_related('program', 'program__vault_item').order_by('scheduled_at')[:20]
    
    schedule_data = [{
        'id': str(s.id),
        'program_id': str(s.program.id),
        'vault_item_name': s.program.vault_item.name if hasattr(s.program.vault_item, 'name') else 'Password',
        'scheduled_at': s.scheduled_at.isoformat(),
        'interval_days': s.interval_days,
        'predicted_strength': s.predicted_strength,
        'recommended_time': s.recommended_time_of_day,
        'is_overdue': s.scheduled_at < timezone.now(),
    } for s in schedules]
    
    return success_response({'schedule': schedule_data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def due_reviews(request):
    """Get programs due for review now."""
    service = MemoryTrainingService(request.user)
    due = service.get_due_reviews()
    
    programs = [service.get_program_progress(p) for p in due]
    
    return success_response({
        'due_count': len(programs),
        'programs': programs,
    })


# =============================================================================
# Settings
# =============================================================================

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def neuro_settings(request):
    """Get or update neuro-feedback settings."""
    settings, created = NeuroFeedbackSettings.objects.get_or_create(user=request.user)
    
    if request.method == 'GET':
        return success_response({
            'settings': {
                'is_enabled': settings.is_enabled,
                'preferred_device_id': str(settings.preferred_device.id) if settings.preferred_device else None,
                'auto_connect': settings.auto_connect,
                'session_duration_minutes': settings.session_duration_minutes,
                'chunk_size': settings.chunk_size,
                'daily_reminder': settings.daily_reminder,
                'reminder_time': settings.reminder_time.isoformat() if settings.reminder_time else None,
                'feedback_mode': settings.feedback_mode,
                'audio_volume': settings.audio_volume,
                'haptic_intensity': settings.haptic_intensity,
                'alpha_threshold': settings.alpha_threshold,
                'binaural_beats_enabled': settings.binaural_beats_enabled,
                'binaural_frequency': settings.binaural_frequency,
            }
        })
    
    elif request.method == 'PUT':
        data = request.data
        
        updatable_fields = [
            'is_enabled', 'auto_connect', 'session_duration_minutes',
            'chunk_size', 'daily_reminder', 'feedback_mode',
            'audio_volume', 'haptic_intensity', 'alpha_threshold',
            'binaural_beats_enabled', 'binaural_frequency',
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(settings, field, data[field])
        
        # Handle device preference
        if 'preferred_device_id' in data:
            if data['preferred_device_id']:
                try:
                    device = EEGDevice.objects.get(
                        id=data['preferred_device_id'],
                        user=request.user
                    )
                    settings.preferred_device = device
                except EEGDevice.DoesNotExist:
                    return error_response("Device not found")
            else:
                settings.preferred_device = None
        
        # Handle reminder time
        if 'reminder_time' in data:
            from datetime import time
            if data['reminder_time']:
                parts = data['reminder_time'].split(':')
                settings.reminder_time = time(int(parts[0]), int(parts[1]))
            else:
                settings.reminder_time = None
        
        settings.save()
        
        return success_response({'message': 'Settings updated successfully'})


# =============================================================================
# Statistics
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def neuro_statistics(request):
    """Get neuro-feedback training statistics."""
    user = request.user
    
    programs = PasswordTrainingProgram.objects.filter(user=user)
    sessions = BrainwaveSession.objects.filter(user=user)
    
    # Calculate stats
    total_programs = programs.count()
    completed_programs = programs.filter(status='completed').count()
    active_programs = programs.filter(status='in_progress').count()
    
    total_sessions = sessions.count()
    total_training_time = sum(s.duration_seconds for s in sessions)
    
    # Average memory strength across all active programs
    active_scores = MemoryStrengthScore.objects.filter(
        program__user=user,
        program__status='in_progress'
    )
    avg_strength = (
        sum(s.strength_score for s in active_scores) / active_scores.count()
        if active_scores.exists() else 0
    )
    
    # Calculate average optimal state time
    avg_optimal_time = (
        sum(s.optimal_state_time for s in sessions) / sessions.count()
        if sessions.exists() else 0
    )
    
    return success_response({
        'statistics': {
            'total_programs': total_programs,
            'completed_programs': completed_programs,
            'active_programs': active_programs,
            'total_sessions': total_sessions,
            'total_training_time_hours': round(total_training_time / 3600, 1),
            'average_memory_strength': round(avg_strength, 3),
            'average_optimal_state_seconds': round(avg_optimal_time, 1),
            'passwords_memorized': completed_programs,
        }
    })
