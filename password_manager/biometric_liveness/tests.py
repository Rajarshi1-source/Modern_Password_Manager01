"""
Biometric Liveness Tests
=========================

Comprehensive tests for liveness detection services.
"""

from django.test import TestCase, TransactionTestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock
import unittest
import numpy as np
import uuid

try:
    from mediapipe.python.solutions import face_mesh as _mp_face_mesh
    _HAS_MP_PYTHON = True
except (ImportError, AttributeError):
    _HAS_MP_PYTHON = False

from .models import (
    LivenessProfile, LivenessSession, LivenessChallenge,
    LivenessSettings
)
from .services import (
    MicroExpressionAnalyzer, GazeTrackingService,
    PulseOximetryService, ThermalImagingService,
    DeepfakeDetector, LivenessSessionService
)
from .ml_models import (
    ActionUnitDetector, GazeEstimator,
    FakeTextureClassifier, RPPGExtractor
)

User = get_user_model()


# Mock Celery tasks to avoid Redis connection during tests
def mock_celery_delay(*args, **kwargs):
    """Mock for Celery task.delay() to avoid Redis."""
    return MagicMock(id='mock-task-id')


@patch('ml_dark_web.tasks.monitor_user_credentials.delay', mock_celery_delay)
class LivenessModelTests(TestCase):
    """Tests for liveness data models."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_liveness_profile(self):
        """Test creating a liveness profile."""
        profile = LivenessProfile.objects.create(user=self.user)
        self.assertFalse(profile.is_calibrated)
        self.assertEqual(profile.calibration_samples, 0)
    
    def test_create_liveness_session(self):
        """Test creating a liveness session."""
        session = LivenessSession.objects.create(
            user=self.user,
            context='login'
        )
        self.assertEqual(session.status, 'pending')
        self.assertIsNotNone(session.id)
    
    def test_create_liveness_settings(self):
        """Test creating liveness settings."""
        settings = LivenessSettings.objects.create(user=self.user)
        self.assertFalse(settings.enable_on_login)
        self.assertTrue(settings.enable_on_sensitive_actions)


class MicroExpressionAnalyzerTests(TestCase):
    """Tests for MicroExpressionAnalyzer service."""
    
    def setUp(self):
        self.analyzer = MicroExpressionAnalyzer()
    
    def test_initialization(self):
        """Test analyzer initialization."""
        self.assertIsNotNone(self.analyzer)
    
    def test_extract_action_units_empty_landmarks(self):
        """Test AU extraction with empty landmarks."""
        result = self.analyzer.extract_action_units(None)
        self.assertEqual(result, {})
    
    @unittest.skipUnless(_HAS_MP_PYTHON, "mediapipe.python.solutions not available")
    @patch('mediapipe.python.solutions.face_mesh.FaceMesh')
    def test_extract_landmarks(self, mock_face_mesh):
        """Test landmark extraction from image."""
        mock_instance = MagicMock()
        mock_face_mesh.return_value = mock_instance
        mock_instance.process.return_value = MagicMock(multi_face_landmarks=None)
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = self.analyzer.extract_landmarks(frame)
        
        # Should return None if no face detected
        self.assertIsNone(result)


class GazeTrackingServiceTests(TestCase):
    """Tests for GazeTrackingService."""
    
    def setUp(self):
        self.service = GazeTrackingService()
    
    def test_initialization(self):
        """Test service initialization."""
        self.assertIsNotNone(self.service)
    
    def test_generate_cognitive_task(self):
        """Test cognitive task generation."""
        task = self.service.generate_cognitive_task()
        self.assertIsNotNone(task)
        self.assertIn('target_positions', dir(task) or hasattr(task, 'target_positions'))
    
    def test_estimate_gaze_no_frame(self):
        """Test gaze estimation with no frame."""
        result = self.service.estimate_gaze(None, None)
        self.assertIsNone(result)


class PulseOximetryServiceTests(TestCase):
    """Tests for PulseOximetryService."""
    
    def setUp(self):
        self.service = PulseOximetryService()
    
    def test_initialization(self):
        """Test service initialization."""
        self.assertIsNotNone(self.service)
        self.assertEqual(self.service.frame_count, 0)
    
    def test_process_frame(self):
        """Test frame processing."""
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        result = self.service.process_frame(frame, 0)
        
        self.assertIsNotNone(result)
        self.assertIn('ppg_value', dir(result) or hasattr(result, 'ppg_value'))
    
    def test_reset(self):
        """Test service reset."""
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        self.service.process_frame(frame, 0)
        
        self.service.reset()
        self.assertEqual(self.service.frame_count, 0)


class ThermalImagingServiceTests(TestCase):
    """Tests for ThermalImagingService."""
    
    def setUp(self):
        self.service = ThermalImagingService({'thermal_enabled': True})
    
    def test_initialization(self):
        """Test service initialization."""
        self.assertIsNotNone(self.service)
    
    def test_is_available(self):
        """Test availability check."""
        self.assertTrue(self.service.is_available())


class DeepfakeDetectorTests(TestCase):
    """Tests for DeepfakeDetector."""
    
    def setUp(self):
        self.detector = DeepfakeDetector()
    
    def test_initialization(self):
        """Test detector initialization."""
        self.assertIsNotNone(self.detector)
    
    def test_analyze_frame(self):
        """Test frame analysis."""
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        result = self.detector.analyze_frame(frame)
        
        self.assertIsNotNone(result)
        self.assertIn('fake_probability', dir(result) or hasattr(result, 'fake_probability'))
    
    def test_get_liveness_score(self):
        """Test liveness score calculation."""
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        self.detector.analyze_frame(frame)
        
        score = self.detector.get_liveness_score()
        self.assertTrue(0 <= score <= 1)
    
    def test_reset(self):
        """Test detector reset."""
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        self.detector.analyze_frame(frame)
        
        self.detector.reset()
        self.assertEqual(len(self.detector.frame_history), 0)


class ActionUnitDetectorTests(TestCase):
    """Tests for ActionUnitDetector ML model."""
    
    def setUp(self):
        self.detector = ActionUnitDetector()
    
    def test_initialization(self):
        """Test detector initialization."""
        self.assertIsNotNone(self.detector)
    
    def test_detect_empty_image(self):
        """Test detection with empty image."""
        result = self.detector.detect(None)
        self.assertIsInstance(result, dict)


class GazeEstimatorTests(TestCase):
    """Tests for GazeEstimator ML model."""
    
    def setUp(self):
        self.estimator = GazeEstimator()
    
    def test_initialization(self):
        """Test estimator initialization."""
        self.assertIsNotNone(self.estimator)
    
    def test_estimate_no_frame(self):
        """Test estimation with no frame."""
        result = self.estimator.estimate(None)
        self.assertIsNone(result)


class FakeTextureClassifierTests(TestCase):
    """Tests for FakeTextureClassifier ML model."""
    
    def setUp(self):
        self.classifier = FakeTextureClassifier()
    
    def test_initialization(self):
        """Test classifier initialization."""
        self.assertIsNotNone(self.classifier)
    
    def test_classify_random_image(self):
        """Test classification of random image."""
        image = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
        result = self.classifier.classify(image)
        
        self.assertIn('fake_probability', result)
        self.assertIn('confidence', result)


class RPPGExtractorTests(TestCase):
    """Tests for RPPGExtractor ML model."""
    
    def setUp(self):
        self.extractor = RPPGExtractor()
    
    def test_initialization(self):
        """Test extractor initialization."""
        self.assertIsNotNone(self.extractor)
        self.assertEqual(self.extractor.frame_count, 0)
    
    def test_process_frame(self):
        """Test frame processing."""
        frame = np.random.randint(100, 200, (480, 640, 3), dtype=np.uint8)
        result = self.extractor.process_frame(frame)
        
        self.assertIsNotNone(result)
        self.assertIn('ppg_value', result)
    
    def test_reset(self):
        """Test extractor reset."""
        frame = np.random.randint(100, 200, (480, 640, 3), dtype=np.uint8)
        self.extractor.process_frame(frame)
        
        self.extractor.reset()
        self.assertEqual(self.extractor.frame_count, 0)


@patch('ml_dark_web.tasks.monitor_user_credentials.delay', mock_celery_delay)
class LivenessAPITests(APITestCase):
    """Tests for liveness REST API endpoints."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='apiuser',
            email='api@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_start_session(self):
        """Test starting a liveness session."""
        url = reverse('biometric_liveness:start_session')
        response = self.client.post(url, {'context': 'login'})
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('session_id', response.data)
    
    def test_get_profile(self):
        """Test getting liveness profile."""
        url = reverse('biometric_liveness:get_profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_get_settings(self):
        """Test getting liveness settings."""
        url = reverse('biometric_liveness:settings')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_update_settings(self):
        """Test updating liveness settings."""
        url = reverse('biometric_liveness:settings')
        response = self.client.put(url, {
            'enable_on_login': False
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_get_history(self):
        """Test getting verification history."""
        url = reverse('biometric_liveness:get_history')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('sessions', response.data)

    def test_challenge_response_rejects_non_owner(self):
        """A user cannot submit a challenge response to another user's session."""
        start = self.client.post(
            reverse('biometric_liveness:start_session'), {'context': 'login'})
        session_id = start.data['session_id']
        other = User.objects.create_user(
            username='bob', email='bob@example.com', password='testpass123')
        self.client.force_authenticate(user=other)
        resp = self.client.post(
            reverse('biometric_liveness:submit_challenge_response'),
            {'session_id': session_id, 'response': {'gaze_data': []}}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class ChallengeResponseFlowTests(TestCase):
    """Gaze cognitive challenge-response is scored and gates the verdict."""

    def setUp(self):
        self.service = LivenessSessionService()

    def _good_gaze_data(self, task):
        data, t = [], 100.0
        for (tx, ty) in task.target_positions:
            for k in range(6):
                data.append({'x': tx, 'y': ty, 'timestamp_ms': t,
                             'confidence': 0.9, 'is_fixation': k > 1})
                t += 40.0
        return data

    def _inject_pulse(self, session, n=6):
        """Give the session a real 2nd modality without processing 100+ frames."""
        from .services.pulse_oximetry_service import PulseReading
        session['pulse_readings'] = [
            PulseReading(timestamp_ms=i * 33.0, frame_number=i, rgb_means=(0.0, 0.0, 0.0),
                         ppg_value=0.0, heart_rate_bpm=72.0, heart_rate_variability=30.0,
                         spo2_estimate=None, signal_quality=0.8)
            for i in range(n)
        ]

    def test_client_challenges_include_render_data(self):
        info = self.service.create_session(user_id=1)
        self.assertTrue(all('data' in c for c in info['challenges']))

    def test_gaze_response_recorded_and_gates(self):
        info = self.service.create_session(user_id=1)
        sid = info['session_id']
        session = self.service.active_sessions[sid]
        gaze_ch = next(c for c in session['challenges'] if c['type'] == 'gaze')
        out = self.service.submit_challenge_response(sid, {
            'sequence': gaze_ch['sequence'],
            'gaze_data': self._good_gaze_data(gaze_ch['cognitive_task']),
        })
        self.assertIn('passed', out)
        self.assertEqual(len(session['gaze_task_results']), 1)
        self._inject_pulse(session)
        result = self.service.complete_session(sid)
        self.assertIn('gaze', result.details['modalities_present'])
        self.assertIn('pulse', result.details['modalities_present'])
        self.assertNotEqual(result.verdict, 'INSUFFICIENT_SIGNAL')

    def test_empty_gaze_response_not_recorded(self):
        info = self.service.create_session(user_id=1)
        sid = info['session_id']
        session = self.service.active_sessions[sid]
        gaze_ch = next(c for c in session['challenges'] if c['type'] == 'gaze')
        out = self.service.submit_challenge_response(sid, {'sequence': gaze_ch['sequence'], 'gaze_data': []})
        self.assertFalse(out['passed'])
        # Empty gaze is not recorded, so it cannot count as a present modality.
        self.assertEqual(len(session['gaze_task_results']), 0)
        self._inject_pulse(session)
        result = self.service.complete_session(sid)
        self.assertNotIn('gaze', result.details['modalities_present'])
        self.assertEqual(result.verdict, 'INSUFFICIENT_SIGNAL')

    def test_no_response_fails_closed(self):
        sid = self.service.create_session(user_id=1)['session_id']
        result = self.service.complete_session(sid)
        self.assertEqual(result.verdict, 'INSUFFICIENT_SIGNAL')
        self.assertFalse(result.is_verified)

    def test_unknown_session_returns_error(self):
        out = self.service.submit_challenge_response('does-not-exist', {'gaze_data': []})
        self.assertIn('error', out)
