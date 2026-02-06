"""
EEG Device Service
==================

Manages EEG headset device connections, calibration, and data streaming.

Supported devices:
- Muse (1, 2, S)
- NeuroSky MindWave
- OpenBCI
- Emotiv Insight

@author Password Manager Team
@created 2026-02-07
"""

import logging
import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from django.utils import timezone
from django.db import transaction

from ..models import EEGDevice, NeuroFeedbackSettings

logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    """EEG device information from discovery."""
    device_id: str
    device_type: str
    name: str
    signal_strength: int
    firmware_version: str = ""
    battery_level: int = 100


@dataclass
class SignalQuality:
    """EEG signal quality metrics."""
    overall: float  # 0-1
    electrode_contacts: Dict[str, float]  # Per-electrode quality
    noise_level: float
    artifact_ratio: float
    is_usable: bool


class EEGDeviceService:
    """
    Service for managing EEG device connections and data streaming.
    """
    
    # Device SDK adapters (would be implemented per device type)
    DEVICE_ADAPTERS = {
        'muse': 'MuseAdapter',
        'muse_2': 'MuseAdapter',
        'muse_s': 'MuseAdapter',
        'neurosky': 'NeuroSkyAdapter',
        'openbci': 'OpenBCIAdapter',
        'emotiv': 'EmotivAdapter',
    }
    
    # Default calibration parameters
    DEFAULT_CALIBRATION = {
        'baseline_duration_seconds': 60,
        'eyes_open_duration': 30,
        'eyes_closed_duration': 30,
        'artifact_threshold': 100,  # microvolts
    }
    
    def __init__(self, user):
        self.user = user
        self._active_connections = {}
    
    # =========================================================================
    # Device Discovery
    # =========================================================================
    
    async def discover_devices(self, timeout_seconds: int = 10) -> List[DeviceInfo]:
        """
        Scan for available EEG devices via Bluetooth.
        
        Returns list of discovered devices.
        """
        discovered = []
        
        # In production, this would use platform-specific BLE scanning
        # For now, return simulated discovery results
        logger.info(f"Scanning for EEG devices for {timeout_seconds}s...")
        
        # Simulated device discovery (replace with actual BLE scan)
        # Each adapter would implement its own discovery logic
        
        return discovered
    
    # =========================================================================
    # Device Registration
    # =========================================================================
    
    @transaction.atomic
    def register_device(
        self,
        device_id: str,
        device_type: str,
        device_name: str,
        firmware_version: str = ""
    ) -> EEGDevice:
        """
        Register a new EEG device for the user.
        """
        # Check if device already registered
        existing = EEGDevice.objects.filter(
            user=self.user,
            device_id=device_id
        ).first()
        
        if existing:
            # Update existing device
            existing.device_name = device_name
            existing.device_type = device_type
            existing.firmware_version = firmware_version
            existing.status = 'paired'
            existing.save()
            logger.info(f"Updated existing device: {device_id}")
            return existing
        
        # Create new device
        device = EEGDevice.objects.create(
            user=self.user,
            device_id=device_id,
            device_type=device_type,
            device_name=device_name,
            firmware_version=firmware_version,
            status='paired',
        )
        
        logger.info(f"Registered new EEG device: {device_name} ({device_type})")
        return device
    
    def unregister_device(self, device_id: uuid.UUID) -> bool:
        """Remove a registered device."""
        deleted, _ = EEGDevice.objects.filter(
            id=device_id,
            user=self.user
        ).delete()
        
        return deleted > 0
    
    def get_user_devices(self) -> List[EEGDevice]:
        """Get all devices registered to the user."""
        return list(EEGDevice.objects.filter(user=self.user).order_by('-last_connected_at'))
    
    def get_preferred_device(self) -> Optional[EEGDevice]:
        """Get user's preferred device, or most recently used."""
        try:
            settings = NeuroFeedbackSettings.objects.get(user=self.user)
            if settings.preferred_device:
                return settings.preferred_device
        except NeuroFeedbackSettings.DoesNotExist:
            pass
        
        # Return most recently connected device
        return EEGDevice.objects.filter(
            user=self.user,
            status__in=['ready', 'paired']
        ).order_by('-last_connected_at').first()
    
    # =========================================================================
    # Device Connection
    # =========================================================================
    
    async def connect(self, device: EEGDevice) -> bool:
        """
        Establish connection to an EEG device.
        
        Returns True if connection successful.
        """
        try:
            device.status = 'calibrating'
            device.save()
            
            # Get appropriate adapter for device type
            adapter_name = self.DEVICE_ADAPTERS.get(device.device_type)
            if not adapter_name:
                raise ValueError(f"Unsupported device type: {device.device_type}")
            
            # In production: Initialize device SDK and connect
            # adapter = self._get_adapter(adapter_name)
            # connected = await adapter.connect(device.device_id)
            
            # Simulated connection success
            device.status = 'ready'
            device.last_connected_at = timezone.now()
            device.save()
            
            self._active_connections[str(device.id)] = {
                'device': device,
                'connected_at': timezone.now(),
                'streaming': False,
            }
            
            logger.info(f"Connected to device: {device.device_name}")
            return True
            
        except Exception as e:
            device.status = 'error'
            device.save()
            logger.error(f"Failed to connect to device {device.device_name}: {e}")
            return False
    
    async def disconnect(self, device: EEGDevice) -> bool:
        """Disconnect from an EEG device."""
        try:
            device_key = str(device.id)
            
            if device_key in self._active_connections:
                # Stop any active streaming
                # In production: adapter.disconnect()
                del self._active_connections[device_key]
            
            device.status = 'disconnected'
            device.save()
            
            logger.info(f"Disconnected from device: {device.device_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting from device: {e}")
            return False
    
    # =========================================================================
    # Calibration
    # =========================================================================
    
    async def calibrate(
        self,
        device: EEGDevice,
        duration_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        Run calibration routine to establish user's baseline brain state.
        
        Calibration involves:
        1. Eyes-open baseline (measure alpha suppression)
        2. Eyes-closed baseline (measure alpha peak)
        3. Noise floor measurement
        """
        device.status = 'calibrating'
        device.save()
        
        try:
            calibration_result = {
                'success': False,
                'baseline_alpha': None,
                'baseline_theta': None,
                'noise_floor': None,
                'signal_quality': None,
                'recommendations': [],
            }
            
            # In production: Collect actual EEG data during calibration
            # eyes_closed_data = await self._collect_eeg(device, duration_seconds // 2)
            # eyes_open_data = await self._collect_eeg(device, duration_seconds // 2)
            
            # Simulated calibration results
            import random
            calibration_result['baseline_alpha'] = 8.0 + random.random() * 4  # 8-12 Hz range
            calibration_result['baseline_theta'] = 4.0 + random.random() * 4  # 4-8 Hz range
            calibration_result['noise_floor'] = 0.1 + random.random() * 0.1
            calibration_result['signal_quality'] = 0.7 + random.random() * 0.3
            calibration_result['success'] = calibration_result['signal_quality'] >= 0.7
            
            if calibration_result['success']:
                # Store calibration data
                device.baseline_alpha = calibration_result['baseline_alpha']
                device.baseline_theta = calibration_result['baseline_theta']
                device.calibration_data = {
                    'calibrated_at': timezone.now().isoformat(),
                    'noise_floor': calibration_result['noise_floor'],
                    'signal_quality': calibration_result['signal_quality'],
                }
                device.status = 'ready'
                
                calibration_result['recommendations'] = [
                    "Calibration successful!",
                    f"Your optimal alpha frequency: {calibration_result['baseline_alpha']:.1f} Hz",
                ]
            else:
                device.status = 'error'
                calibration_result['recommendations'] = [
                    "Signal quality too low. Please ensure good electrode contact.",
                    "Try adjusting the headband position.",
                    "Make sure you're in a quiet environment.",
                ]
            
            device.save()
            return calibration_result
            
        except Exception as e:
            device.status = 'error'
            device.save()
            logger.error(f"Calibration failed: {e}")
            return {'success': False, 'error': str(e)}
    
    # =========================================================================
    # Signal Quality
    # =========================================================================
    
    async def get_signal_quality(self, device: EEGDevice) -> SignalQuality:
        """Get current signal quality from device."""
        
        # In production: Read actual signal quality from device
        # quality_data = await adapter.get_signal_quality()
        
        # Simulated signal quality
        import random
        
        electrode_contacts = {
            'AF7': 0.7 + random.random() * 0.3,
            'AF8': 0.7 + random.random() * 0.3,
            'TP9': 0.6 + random.random() * 0.4,
            'TP10': 0.6 + random.random() * 0.4,
        }
        
        overall = sum(electrode_contacts.values()) / len(electrode_contacts)
        
        return SignalQuality(
            overall=overall,
            electrode_contacts=electrode_contacts,
            noise_level=random.random() * 0.3,
            artifact_ratio=random.random() * 0.2,
            is_usable=overall >= device.signal_quality_threshold,
        )
    
    # =========================================================================
    # Battery
    # =========================================================================
    
    async def get_battery_level(self, device: EEGDevice) -> int:
        """Get device battery level (0-100)."""
        # In production: Read from device
        import random
        battery = random.randint(20, 100)
        
        device.battery_level = battery
        device.save(update_fields=['battery_level'])
        
        return battery
