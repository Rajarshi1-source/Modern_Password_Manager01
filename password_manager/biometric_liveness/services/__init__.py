"""
Biometric Liveness Services
============================

Core services for deepfake-resistant biometric authentication.
"""

from .micro_expression_analyzer import MicroExpressionAnalyzer
from .gaze_tracking_service import GazeTrackingService
from .pulse_oximetry_service import PulseOximetryService
from .thermal_imaging_service import ThermalImagingService
from .deepfake_detector import DeepfakeDetector
from .liveness_session_service import LivenessSessionService

__all__ = [
    'MicroExpressionAnalyzer',
    'GazeTrackingService',
    'PulseOximetryService',
    'ThermalImagingService',
    'DeepfakeDetector',
    'LivenessSessionService',
]
