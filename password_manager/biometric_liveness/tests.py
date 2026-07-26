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
import os
import unittest
import numpy as np
import uuid
from collections import deque

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

    def test_action_units_are_deterministic_not_fabricated(self):
        """Unimplemented AU intensities must be 0.0, never random values.

        The placeholder AU methods previously returned np.random.uniform(...), a
        fabricated biometric signal sitting one wiring step from the verdict. They
        must be deterministic (0.0 = inactive) until real geometry lands, matching
        the never-fabricate stance of the landmark/gaze placeholders.
        """
        landmarks = np.zeros((468, 3), dtype=np.float64)
        first = self.analyzer.extract_action_units(landmarks)
        second = self.analyzer.extract_action_units(landmarks)
        # No randomness anywhere in the AU pipeline: identical across calls.
        self.assertEqual(first, second)
        # The not-yet-implemented AUs report inactive (0.0), not a random intensity.
        for au in (2, 4, 5, 6, 12, 25, 26, 45):
            self.assertEqual(first[au], 0.0)

    def test_asymmetry_is_deterministic_not_fabricated(self):
        """The asymmetry stub must return a fixed 0.0, not a random value.

        The previous np.random.uniform(0.1, 0.4) fabricated a perfect asymmetry
        score every call (that band maps to 1.0 in get_liveness_score).
        """
        self.assertEqual(self.analyzer._calculate_asymmetry({}), 0.0)
        self.assertEqual(self.analyzer._calculate_asymmetry({1: 0.5}), 0.0)
    
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

    def test_answer_task_not_failed_by_missing_path_sequence(self):
        """A task without an expected trajectory must not be auto-failed by the
        path-similarity check (it returns 0.0 when expected_sequence is absent)."""
        from .services.gaze_tracking_service import (
            CognitiveTask, CognitiveTaskType, GazePoint)
        task = CognitiveTask(
            task_type=CognitiveTaskType.FIND_OBJECT, instruction='x',
            target_positions=[(0.5, 0.5)], time_limit_ms=6000,
            expected_sequence=None, correct_answer='3')
        pts = [GazePoint(x=0.5, y=0.5, timestamp_ms=i * 40.0,
                         confidence=0.9, is_fixation=True) for i in range(6)]
        # Isolate the path-sequence guard: hold accuracy/human above threshold.
        self.service._calculate_gaze_accuracy = lambda *a, **k: 0.9
        self.service._calculate_human_likelihood = lambda *a, **k: 0.9
        res = self.service.validate_task_response(task, pts, user_answer='3')
        self.assertEqual(res.gaze_path_similarity, 0.0)
        self.assertTrue(res.is_passed)  # passes on accuracy + answer, not path

    def test_reaction_time_is_not_absolute_epoch_timestamp(self):
        """reaction_time_ms must not be the first sample's absolute epoch time.

        It is a duration field; storing an epoch timestamp (~1.7e12 ms) there is
        meaningless and would mislead any future consumer.
        """
        from .services.gaze_tracking_service import (
            CognitiveTask, CognitiveTaskType, GazePoint)
        task = CognitiveTask(
            task_type=CognitiveTaskType.FOLLOW_TARGET, instruction='x',
            target_positions=[(0.5, 0.5)], time_limit_ms=5000,
            expected_sequence=[0])
        epoch_ms = 1_700_000_000_000.0
        pts = [GazePoint(x=0.5, y=0.5, timestamp_ms=epoch_ms + i * 40.0,
                         confidence=0.9, is_fixation=True) for i in range(6)]
        res = self.service.validate_task_response(task, pts)
        self.assertEqual(res.reaction_time_ms, 0.0)
        self.assertNotEqual(res.reaction_time_ms, epoch_ms)


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

    def test_submit_frame_rejects_non_owner(self):
        """A user cannot submit frames to another user's session.

        Locks the in-memory (DB-query-free) ownership check on the hot frame path
        against a session-id-guessing cross-user injection.
        """
        start = self.client.post(
            reverse('biometric_liveness:start_session'), {'context': 'login'})
        session_id = start.data['session_id']
        other = User.objects.create_user(
            username='carol', email='carol@example.com', password='testpass123')
        self.client.force_authenticate(user=other)
        resp = self.client.post(
            reverse('biometric_liveness:submit_frame'),
            {'session_id': session_id, 'frame': 'AAAA', 'width': 4, 'height': 4},
            format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_challenge_response_on_completed_session_returns_409(self):
        """A challenge response to a terminal session mirrors complete's 409.

        A session-lifecycle conflict (already completed) must not be reported as a
        generic 400 bad request, matching complete_session's status semantics.
        """
        start = self.client.post(
            reverse('biometric_liveness:start_session'), {'context': 'login'})
        session_id = start.data['session_id']
        # No estimator loaded -> completes as INSUFFICIENT_SIGNAL (terminal), no raise.
        complete = self.client.post(
            reverse('biometric_liveness:complete_session'),
            {'session_id': session_id}, format='json')
        self.assertEqual(complete.status_code, status.HTTP_200_OK)
        resp = self.client.post(
            reverse('biometric_liveness:submit_challenge_response'),
            {'session_id': session_id, 'response': {}}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        # The internal routing marker must not leak into the client payload.
        self.assertNotIn('state_conflict', resp.data)

    def test_complete_incomplete_gaze_returns_retryable_code(self):
        """Incomplete gaze must map to a distinct, retryable code, not the same
        invalid_session_state as terminal errors."""
        from .services.liveness_session_service import GazeChallengeIncompleteError
        start = self.client.post(
            reverse('biometric_liveness:start_session'), {'context': 'login'})
        session_id = start.data['session_id']
        with patch('biometric_liveness.views.get_session_service') as gss:
            gss.return_value.complete_session.side_effect = \
                GazeChallengeIncompleteError('Required gaze challenge incomplete')
            resp = self.client.post(
                reverse('biometric_liveness:complete_session'),
                {'session_id': session_id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data['error'], 'required_challenge_incomplete')
        self.assertTrue(resp.data.get('retryable'))

    def test_session_busy_maps_to_retryable_409(self):
        """A cross-process lock timeout (SessionLockError) maps to a retryable
        409 session_busy, not a 500 -- so the client retries rather than fails.
        The WS consumer emits the same session_busy envelope (symmetric handler).
        """
        from .services.liveness_session_service import SessionLockError
        start = self.client.post(
            reverse('biometric_liveness:start_session'), {'context': 'login'})
        session_id = start.data['session_id']
        with patch('biometric_liveness.views.get_session_service') as gss:
            gss.return_value.complete_session.side_effect = SessionLockError('busy')
            resp = self.client.post(
                reverse('biometric_liveness:complete_session'),
                {'session_id': session_id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data['error'], 'session_busy')
        self.assertTrue(resp.data.get('retryable'))
        # Retry-After lets generic HTTP clients/proxies back off on their own,
        # rather than hot-looping because they cannot read our body flag.
        self.assertEqual(resp['Retry-After'], '1')

    def test_start_session_db_failure_discards_in_memory_session(self):
        """A DB-create failure must not leak the in-memory session's capacity slot."""
        from django.db import DatabaseError
        from .views import get_session_service
        service = get_session_service()
        before = len(service.active_sessions)
        with patch.object(LivenessSession.objects, 'create',
                          side_effect=DatabaseError('boom')):
            resp = self.client.post(
                reverse('biometric_liveness:start_session'), {'context': 'login'})
        self.assertEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        # The orphaned in-memory session was discarded, not left holding a slot.
        self.assertEqual(len(service.active_sessions), before)

    def test_hardware_spo2_rest_relay_accepts_a_reading(self):
        """The REST relay shares the WS path: a real reading is ingested + accepted."""
        start = self.client.post(
            reverse('biometric_liveness:start_session'), {'context': 'login'})
        session_id = start.data['session_id']
        resp = self.client.post(
            reverse('biometric_liveness:submit_hardware_spo2'),
            {'session_id': session_id, 'spo2': 98.0, 'quality': 0.9}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['accepted'])

    def test_hardware_spo2_rest_rejects_non_owner(self):
        """A user cannot relay SpO2 into another user's session."""
        start = self.client.post(
            reverse('biometric_liveness:start_session'), {'context': 'login'})
        session_id = start.data['session_id']
        other = User.objects.create_user(
            username='dave', email='dave@example.com', password='testpass123')
        self.client.force_authenticate(user=other)
        resp = self.client.post(
            reverse('biometric_liveness:submit_hardware_spo2'),
            {'session_id': session_id, 'spo2': 98.0}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_hardware_spo2_rest_on_completed_session_returns_409(self):
        """SpO2 relayed to a terminal session is a 409 lifecycle conflict, not 400."""
        start = self.client.post(
            reverse('biometric_liveness:start_session'), {'context': 'login'})
        session_id = start.data['session_id']
        self.client.post(
            reverse('biometric_liveness:complete_session'),
            {'session_id': session_id}, format='json')
        resp = self.client.post(
            reverse('biometric_liveness:submit_hardware_spo2'),
            {'session_id': session_id, 'spo2': 98.0}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        # The internal routing marker must not leak into the client payload.
        self.assertNotIn('state_conflict', resp.data)

    def test_persist_session_result_writes_status_and_verdict(self):
        """The shared persistence helper writes status AND the nuanced verdict.

        The WS consumer uses this on completion; without it a WS-completed
        session stays pending/in_progress and would keep accepting reconnects.
        """
        from .views import persist_session_result
        from .services.liveness_session_service import SessionResult
        row = LivenessSession.objects.create(user=self.user, context='login')
        persist_session_result(SessionResult(
            session_id=str(row.id), is_verified=True, overall_liveness_score=0.91,
            deepfake_probability=0.02, confidence=0.4, micro_expression_score=0.0,
            gaze_tracking_score=0.9, pulse_oximetry_score=0.8, thermal_score=0.0,
            texture_artifact_score=0.98, total_frames_processed=42,
            duration_ms=1000.0, verdict='HIGH_CONFIDENCE_LIVE', details={}))
        row.refresh_from_db()
        self.assertEqual(row.status, 'passed')
        self.assertEqual(row.verdict, 'HIGH_CONFIDENCE_LIVE')
        self.assertEqual(row.total_frames_processed, 42)
        # A terminal row must carry its completion timestamp, not stay None.
        self.assertIsNotNone(row.completed_at)
        # Every score field must map correctly -- distinct values so a dropped or
        # swapped assignment is caught.
        self.assertEqual(row.overall_liveness_score, 0.91)
        self.assertEqual(row.deepfake_probability, 0.02)
        self.assertEqual(row.confidence, 0.4)
        self.assertEqual(row.micro_expression_score, 0.0)
        self.assertEqual(row.gaze_tracking_score, 0.9)
        self.assertEqual(row.pulse_oximetry_score, 0.8)
        self.assertEqual(row.thermal_score, 0.0)
        self.assertEqual(row.texture_artifact_score, 0.98)

    def test_persist_db_error_enqueues_durable_retry(self):
        """A transient DB failure hands the verdict to a durable retry queue rather
        than silently losing it (closes the 'silent verdict loss' finding)."""
        from .views import persist_session_result
        from .services.liveness_session_service import SessionResult
        from django.db import DatabaseError
        result = SessionResult(
            session_id=str(uuid.uuid4()), is_verified=False, overall_liveness_score=0.0,
            deepfake_probability=0.0, confidence=0.0, micro_expression_score=0.0,
            gaze_tracking_score=0.0, pulse_oximetry_score=0.0, thermal_score=0.0,
            texture_artifact_score=0.0, total_frames_processed=0,
            duration_ms=0.0, verdict='INSUFFICIENT_SIGNAL', details={})
        with patch.object(LivenessSession.objects, 'get', side_effect=DatabaseError('boom')), \
             patch('biometric_liveness.tasks.retry_persist_liveness_result.delay') as mock_delay:
            persist_session_result(result)  # must not raise
        # The verdict was queued for durable retry, carrying enough to re-apply it.
        mock_delay.assert_called_once()
        payload = mock_delay.call_args[0][0]
        self.assertEqual(payload['verdict'], 'INSUFFICIENT_SIGNAL')
        self.assertEqual(payload['session_id'], result.session_id)

    def test_persist_session_result_accepts_insufficient_signal_verdict(self):
        """INSUFFICIENT_SIGNAL is a real service verdict and must be storable."""
        from .views import persist_session_result
        from .services.liveness_session_service import SessionResult
        row = LivenessSession.objects.create(user=self.user, context='login')
        persist_session_result(SessionResult(
            session_id=str(row.id), is_verified=False, overall_liveness_score=0.0,
            deepfake_probability=0.0, confidence=0.0, micro_expression_score=0.0,
            gaze_tracking_score=0.0, pulse_oximetry_score=0.0, thermal_score=0.0,
            texture_artifact_score=0.0, total_frames_processed=0,
            duration_ms=0.0, verdict='INSUFFICIENT_SIGNAL', details={}))
        row.refresh_from_db()
        self.assertEqual(row.status, 'failed')
        self.assertEqual(row.verdict, 'INSUFFICIENT_SIGNAL')
        # ...and it must be a declared choice, not just an arbitrary string.
        self.assertIn('INSUFFICIENT_SIGNAL', dict(LivenessSession.VERDICT_CHOICES))

    def test_persist_session_result_unknown_row_is_noop(self):
        """Both a malformed id and a valid-but-absent id must be no-ops, not raise."""
        from .views import persist_session_result
        from .services.liveness_session_service import SessionResult

        def _result(sid):
            return SessionResult(
                session_id=sid, is_verified=False, overall_liveness_score=0.0,
                deepfake_probability=0.0, confidence=0.0, micro_expression_score=0.0,
                gaze_tracking_score=0.0, pulse_oximetry_score=0.0, thermal_score=0.0,
                texture_artifact_score=0.0, total_frames_processed=0,
                duration_ms=0.0, verdict='INSUFFICIENT_SIGNAL', details={})
        # Malformed uuid (ValidationError path) ...
        persist_session_result(_result('not-a-uuid'))
        # ... and a well-formed but absent id (LivenessSession.DoesNotExist path).
        persist_session_result(_result(str(uuid.uuid4())))

    def test_persist_unknown_row_does_not_enqueue_retry(self):
        """Permanent failures (bad/absent id) must NOT be queued for retry."""
        from .views import persist_session_result
        from .services.liveness_session_service import SessionResult

        def _result(sid):
            return SessionResult(
                session_id=sid, is_verified=False, overall_liveness_score=0.0,
                deepfake_probability=0.0, confidence=0.0, micro_expression_score=0.0,
                gaze_tracking_score=0.0, pulse_oximetry_score=0.0, thermal_score=0.0,
                texture_artifact_score=0.0, total_frames_processed=0,
                duration_ms=0.0, verdict='INSUFFICIENT_SIGNAL', details={})
        with patch('biometric_liveness.tasks.retry_persist_liveness_result.delay') as mock_delay:
            persist_session_result(_result('not-a-uuid'))          # ValidationError -> no retry
            persist_session_result(_result(str(uuid.uuid4())))     # DoesNotExist -> no retry
        mock_delay.assert_not_called()

    def test_retry_task_applies_result_to_row(self):
        """The durable retry task writes the verdict onto its row, idempotently."""
        from .views import _liveness_result_payload
        from .services.liveness_session_service import SessionResult
        from .tasks import retry_persist_liveness_result
        row = LivenessSession.objects.create(user=self.user, context='login')
        payload = _liveness_result_payload(SessionResult(
            session_id=str(row.id), is_verified=True, overall_liveness_score=0.9,
            deepfake_probability=0.01, confidence=0.4, micro_expression_score=0.0,
            gaze_tracking_score=0.9, pulse_oximetry_score=0.8, thermal_score=0.0,
            texture_artifact_score=0.99, total_frames_processed=10,
            duration_ms=0.0, verdict='HIGH_CONFIDENCE_LIVE', details={}))
        # Run synchronously; applying twice must be idempotent (same terminal row).
        retry_persist_liveness_result.apply(args=[payload]).get()
        retry_persist_liveness_result.apply(args=[payload]).get()
        row.refresh_from_db()
        self.assertEqual(row.status, 'passed')
        self.assertEqual(row.verdict, 'HIGH_CONFIDENCE_LIVE')
        self.assertEqual(row.overall_liveness_score, 0.9)
        self.assertEqual(row.total_frames_processed, 10)

    def test_apply_liveness_result_raises_on_db_error(self):
        """apply_liveness_result surfaces DatabaseError so the caller can retry."""
        from .views import apply_liveness_result, _liveness_result_payload
        from .services.liveness_session_service import SessionResult
        from django.db import DatabaseError
        row = LivenessSession.objects.create(user=self.user, context='login')
        payload = _liveness_result_payload(SessionResult(
            session_id=str(row.id), is_verified=False, overall_liveness_score=0.0,
            deepfake_probability=0.0, confidence=0.0, micro_expression_score=0.0,
            gaze_tracking_score=0.0, pulse_oximetry_score=0.0, thermal_score=0.0,
            texture_artifact_score=0.0, total_frames_processed=0,
            duration_ms=0.0, verdict='INSUFFICIENT_SIGNAL', details={}))
        with patch.object(LivenessSession, 'save', side_effect=DatabaseError('boom')):
            with self.assertRaises(DatabaseError):
                apply_liveness_result(payload)

    def test_persist_db_error_enqueue_failure_does_not_raise(self):
        """If even the retry-enqueue fails (broker down), persist_session_result
        must still not raise -- the client already holds its verdict. (Uses a
        real session row, as in the live flow where start_session created it:
        the enqueue failure now falls through to the FK-backed outbox.)"""
        from .views import persist_session_result
        from .services.liveness_session_service import SessionResult
        from django.db import DatabaseError
        row = LivenessSession.objects.create(user=self.user, context='login')
        result = SessionResult(
            session_id=str(row.id), is_verified=False, overall_liveness_score=0.0,
            deepfake_probability=0.0, confidence=0.0, micro_expression_score=0.0,
            gaze_tracking_score=0.0, pulse_oximetry_score=0.0, thermal_score=0.0,
            texture_artifact_score=0.0, total_frames_processed=0,
            duration_ms=0.0, verdict='INSUFFICIENT_SIGNAL', details={})
        with patch.object(LivenessSession.objects, 'get', side_effect=DatabaseError('boom')), \
             patch('biometric_liveness.tasks.retry_persist_liveness_result.delay',
                   side_effect=Exception('broker down')):
            persist_session_result(result)  # must not raise

    def test_persisted_completed_at_is_real_completion_time(self):
        """The row's completed_at reflects when the session actually completed, not
        when the (possibly retried) write ran -- and re-applying keeps it stable."""
        from .views import _liveness_result_payload, apply_liveness_result
        from .services.liveness_session_service import SessionResult
        from django.utils import timezone as djtz
        from datetime import timedelta
        row = LivenessSession.objects.create(user=self.user, context='login')
        real_completion = djtz.now() - timedelta(hours=2)  # completed 2h ago
        payload = _liveness_result_payload(SessionResult(
            session_id=str(row.id), is_verified=True, overall_liveness_score=0.9,
            deepfake_probability=0.0, confidence=0.4, micro_expression_score=0.0,
            gaze_tracking_score=0.9, pulse_oximetry_score=0.8, thermal_score=0.0,
            texture_artifact_score=0.99, total_frames_processed=10,
            duration_ms=0.0, verdict='HIGH_CONFIDENCE_LIVE', details={},
            completed_at=real_completion))
        apply_liveness_result(payload)
        row.refresh_from_db()
        # Persisted as the real completion time (~2h ago), not now().
        self.assertLess(row.completed_at, djtz.now() - timedelta(minutes=30))
        saved = row.completed_at
        # Re-applying the same payload is idempotent: completed_at does not drift.
        apply_liveness_result(payload)
        row.refresh_from_db()
        self.assertEqual(row.completed_at, saved)

    def test_submit_frame_non_string_frame_is_400(self):
        """A non-string 'frame' is client error, not a 500 (b64decode TypeError)."""
        start = self.client.post(
            reverse('biometric_liveness:start_session'), {'context': 'login'})
        resp = self.client.post(
            reverse('biometric_liveness:submit_frame'),
            {'session_id': start.data['session_id'], 'frame': 12345,
             'width': 4, 'height': 4}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['error'], 'Invalid frame encoding')

    def test_submit_frame_rejects_oversized_dimensions(self):
        """Huge dimensions are rejected before any decode allocation."""
        start = self.client.post(
            reverse('biometric_liveness:start_session'), {'context': 'login'})
        resp = self.client.post(
            reverse('biometric_liveness:submit_frame'),
            {'session_id': start.data['session_id'], 'frame': 'AAAA',
             'width': 50000, 'height': 50000}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['error'], 'Frame dimensions exceed maximum')

    def test_liveness_limit_env_validation(self):
        """Liveness limits fail fast on non-numeric / out-of-range config."""
        from password_manager.settings.base import _liveness_int_env
        from django.core.exceptions import ImproperlyConfigured
        # Uses the default arg (env var unset), so no environment mutation.
        self.assertEqual(_liveness_int_env('LIVENESS_UNSET_X', '42', minimum=1), 42)
        with self.assertRaises(ImproperlyConfigured):
            _liveness_int_env('LIVENESS_UNSET_X', 'abc', minimum=1)   # non-numeric
        with self.assertRaises(ImproperlyConfigured):
            _liveness_int_env('LIVENESS_UNSET_X', '0', minimum=1)     # below minimum
        # A non-negative limit (retention) may be zero.
        self.assertEqual(_liveness_int_env('LIVENESS_UNSET_X', '0', minimum=0), 0)

    def test_liveness_float_env_validation(self):
        """Float liveness thresholds fail fast on non-numeric / out-of-range config."""
        from password_manager.settings.base import _liveness_float_env
        from django.core.exceptions import ImproperlyConfigured
        # Uses the default arg (env var unset), so no environment mutation.
        self.assertEqual(
            _liveness_float_env('LIVENESS_UNSET_F', '0.85', minimum=0.0, maximum=1.0), 0.85)
        with self.assertRaises(ImproperlyConfigured):
            _liveness_float_env('LIVENESS_UNSET_F', 'abc', minimum=0.0, maximum=1.0)   # non-numeric
        with self.assertRaises(ImproperlyConfigured):
            _liveness_float_env('LIVENESS_UNSET_F', '1.5', minimum=0.0, maximum=1.0)   # above max
        with self.assertRaises(ImproperlyConfigured):
            _liveness_float_env('LIVENESS_UNSET_F', '-0.1', minimum=0.0, maximum=1.0)  # below min

    def test_decode_frame_rgb_is_writable(self):
        """The decoded RGB frame must be writable, like the RGBA path.

        np.frombuffer yields a read-only buffer; without an explicit copy a
        detector that preprocesses the frame in place would fail on RGB frames
        while succeeding on RGBA ones.
        """
        import base64
        from .frame_utils import decode_frame
        raw = bytes(2 * 2 * 3)  # 2x2 RGB, all zero
        frame, err = decode_frame(base64.b64encode(raw).decode(), 2, 2)
        self.assertIsNone(err)
        self.assertEqual(frame.shape, (2, 2, 3))
        self.assertTrue(frame.flags.writeable)

    def test_challenge_response_same_owner_ok(self):
        """The owning user can submit a challenge response (shared session store)."""
        start = self.client.post(
            reverse('biometric_liveness:start_session'), {'context': 'login'})
        session_id = start.data['session_id']
        resp = self.client.post(
            reverse('biometric_liveness:submit_challenge_response'),
            {'session_id': session_id, 'response': {}}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('next_challenge', resp.data)


class PersistOutboxTests(TestCase):
    """DB-backed persist outbox: the last-resort net behind the broker retry."""

    def setUp(self):
        """Create the owning user for real LivenessSession rows."""
        self.user = User.objects.create_user(
            username='outboxuser', email='outbox@example.com',
            password='testpass123')

    def _result(self, sid, verdict='HIGH_CONFIDENCE_LIVE', is_verified=True):
        """Build a frozen SessionResult for the given session id."""
        from .services.liveness_session_service import SessionResult
        return SessionResult(
            session_id=sid, is_verified=is_verified, overall_liveness_score=0.9,
            deepfake_probability=0.01, confidence=0.4, micro_expression_score=0.0,
            gaze_tracking_score=0.9, pulse_oximetry_score=0.8, thermal_score=0.0,
            texture_artifact_score=0.99, total_frames_processed=10,
            duration_ms=1000.0, verdict=verdict, details={})

    def _payload(self, sid, **kwargs):
        """Build the JSON-safe persistence payload for the given session id."""
        from .views import _liveness_result_payload
        return _liveness_result_payload(self._result(sid, **kwargs))

    def _session(self):
        """Create a real LivenessSession row (the outbox FK requires one, as in
        the real flow where start_session always created it)."""
        return LivenessSession.objects.create(user=self.user, context='login')

    def test_broker_enqueue_failure_writes_outbox_row(self):
        """DB error + broker enqueue failure records the verdict in the outbox."""
        from .views import persist_session_result
        from .models import LivenessPersistOutbox
        from django.db import DatabaseError
        session = self._session()
        result = self._result(str(session.id), verdict='INSUFFICIENT_SIGNAL',
                              is_verified=False)
        with patch.object(LivenessSession.objects, 'get', side_effect=DatabaseError('boom')), \
             patch('biometric_liveness.tasks.retry_persist_liveness_result.delay',
                   side_effect=Exception('broker down')):
            persist_session_result(result)  # must not raise
        row = LivenessPersistOutbox.objects.get(session_id=result.session_id)
        self.assertEqual(row.status, 'pending')
        self.assertEqual(row.payload['verdict'], 'INSUFFICIENT_SIGNAL')
        self.assertEqual(row.payload['session_id'], result.session_id)

    def test_outbox_not_written_when_enqueue_succeeds(self):
        """A successful broker enqueue must NOT also write an outbox row."""
        from .views import persist_session_result
        from .models import LivenessPersistOutbox
        from django.db import DatabaseError
        result = self._result(str(uuid.uuid4()))
        with patch.object(LivenessSession.objects, 'get', side_effect=DatabaseError('boom')), \
             patch('biometric_liveness.tasks.retry_persist_liveness_result.delay'):
            persist_session_result(result)
        self.assertFalse(LivenessPersistOutbox.objects.exists())

    def test_outbox_write_failure_still_does_not_raise(self):
        """Even with DB, broker AND the outbox write down, persist must not 500."""
        from .views import persist_session_result
        from .models import LivenessPersistOutbox
        from django.db import DatabaseError
        result = self._result(str(uuid.uuid4()))
        with patch.object(LivenessSession.objects, 'get', side_effect=DatabaseError('boom')), \
             patch('biometric_liveness.tasks.retry_persist_liveness_result.delay',
                   side_effect=Exception('broker down')), \
             patch.object(LivenessPersistOutbox.objects, 'update_or_create',
                          side_effect=DatabaseError('still down')):
            persist_session_result(result)  # must not raise

    def test_retry_exhaustion_records_outbox_row(self):
        """Exhausted broker retries fall through to the outbox, not silent loss."""
        from .models import LivenessPersistOutbox
        from .tasks import retry_persist_liveness_result
        from celery.exceptions import MaxRetriesExceededError
        from django.db import DatabaseError
        payload = self._payload(str(self._session().id))
        with patch('biometric_liveness.views.apply_liveness_result',
                   side_effect=DatabaseError('boom')), \
             patch.object(retry_persist_liveness_result, 'retry',
                          side_effect=MaxRetriesExceededError()):
            retry_persist_liveness_result.apply(args=[payload])
        row = LivenessPersistOutbox.objects.get(session_id=payload['session_id'])
        self.assertEqual(row.status, 'pending')
        self.assertIn('exhausted', row.last_error)

    def test_retry_exhaustion_original_error_reraise_records_outbox(self):
        """Celery's REAL exhaustion behavior still lands in the outbox.

        Task.retry(exc=...) does NOT raise MaxRetriesExceededError once the
        budget is spent -- it re-raises the ORIGINAL exception via
        raise_with_context(exc). Catching only MaxRetriesExceededError would
        skip the last-resort net in a real worker and lose the verdict on the
        final retry.
        """
        from .models import LivenessPersistOutbox
        from .tasks import retry_persist_liveness_result
        from django.db import DatabaseError
        payload = self._payload(str(self._session().id))
        with patch('biometric_liveness.views.apply_liveness_result',
                   side_effect=DatabaseError('boom')), \
             patch.object(retry_persist_liveness_result, 'retry',
                          side_effect=DatabaseError('boom')):
            retry_persist_liveness_result.apply(args=[payload])
        row = LivenessPersistOutbox.objects.get(session_id=payload['session_id'])
        self.assertEqual(row.status, 'pending')
        self.assertIn('exhausted', row.last_error)

    def test_retry_with_budget_left_does_not_record_outbox(self):
        """A transient failure with retries remaining stays on the broker layer."""
        from .models import LivenessPersistOutbox
        from .tasks import retry_persist_liveness_result
        from celery.exceptions import Retry
        from django.db import DatabaseError
        payload = self._payload(str(uuid.uuid4()))
        with patch('biometric_liveness.views.apply_liveness_result',
                   side_effect=DatabaseError('boom')), \
             patch.object(retry_persist_liveness_result, 'retry',
                          side_effect=Retry()):
            retry_persist_liveness_result.apply(args=[payload])
        self.assertFalse(LivenessPersistOutbox.objects.exists())

    def test_drain_applies_and_deletes_row(self):
        """The sweeper writes the verdict onto the row and deletes the record."""
        from .models import LivenessPersistOutbox
        from .tasks import drain_liveness_persist_outbox
        row = LivenessSession.objects.create(user=self.user, context='login')
        LivenessPersistOutbox.objects.create(
            session_id=row.id, payload=self._payload(str(row.id)))
        drained = drain_liveness_persist_outbox.apply().get()
        self.assertEqual(drained, 1)
        row.refresh_from_db()
        self.assertEqual(row.status, 'passed')
        self.assertEqual(row.verdict, 'HIGH_CONFIDENCE_LIVE')
        self.assertEqual(row.overall_liveness_score, 0.9)
        # Applied rows are deleted -- nothing biometric lingers in the outbox.
        self.assertFalse(LivenessPersistOutbox.objects.exists())

    def test_drain_is_idempotent_against_duplicate_apply(self):
        """A row racing a broker retry (both applying) converges on one verdict."""
        from .views import apply_liveness_result
        from .models import LivenessPersistOutbox
        from .tasks import drain_liveness_persist_outbox
        row = LivenessSession.objects.create(user=self.user, context='login')
        payload = self._payload(str(row.id))
        apply_liveness_result(payload)  # the broker retry got there first
        LivenessPersistOutbox.objects.create(session_id=row.id, payload=payload)
        drained = drain_liveness_persist_outbox.apply().get()
        self.assertEqual(drained, 1)
        row.refresh_from_db()
        self.assertEqual(row.status, 'passed')
        self.assertFalse(LivenessPersistOutbox.objects.exists())

    def test_deleting_session_cascades_outbox_rows(self):
        """Deleting a session removes its outbox payload -- pending AND abandoned.

        The outbox stores biometric-derived verdict data; a cascading FK (not a
        raw UUID column) guarantees it never outlives its session, even for
        abandoned rows that the sweeper no longer examines.
        """
        from .models import LivenessPersistOutbox
        pending_session = self._session()
        abandoned_session = self._session()
        LivenessPersistOutbox.objects.create(
            session_id=pending_session.id,
            payload=self._payload(str(pending_session.id)))
        LivenessPersistOutbox.objects.create(
            session_id=abandoned_session.id,
            payload=self._payload(str(abandoned_session.id)),
            status='abandoned', attempts=99)
        pending_session.delete()
        abandoned_session.delete()
        self.assertFalse(LivenessPersistOutbox.objects.exists())

    def test_drain_drops_row_when_session_vanishes_mid_sweep(self):
        """A session deleted between fetch and apply is dropped, not retried."""
        from .models import LivenessPersistOutbox
        from .tasks import drain_liveness_persist_outbox
        session = self._session()
        LivenessPersistOutbox.objects.create(
            session_id=session.id, payload=self._payload(str(session.id)))
        with patch('biometric_liveness.views.apply_liveness_result',
                   side_effect=LivenessSession.DoesNotExist()):
            drained = drain_liveness_persist_outbox.apply().get()
        self.assertEqual(drained, 0)
        # Permanent failure: the record is removed (a deleted session's verdict
        # has no home, and retaining it would be a privacy liability).
        self.assertFalse(LivenessPersistOutbox.objects.exists())

    def test_drain_transient_failure_keeps_row_and_counts_attempt(self):
        """A transient DB failure leaves the row pending with attempts+1."""
        from .models import LivenessPersistOutbox
        from .tasks import drain_liveness_persist_outbox
        from django.db import DatabaseError
        sid = str(self._session().id)
        LivenessPersistOutbox.objects.create(
            session_id=sid, payload=self._payload(sid))
        with patch('biometric_liveness.views.apply_liveness_result',
                   side_effect=DatabaseError('flaky')):
            drained = drain_liveness_persist_outbox.apply().get()
        self.assertEqual(drained, 0)
        row = LivenessPersistOutbox.objects.get(session_id=sid)
        self.assertEqual(row.status, 'pending')
        self.assertEqual(row.attempts, 1)
        self.assertIn('flaky', row.last_error)

    def test_drain_abandons_row_after_max_attempts(self):
        """Attempts exhausting the cap abandon the row; later sweeps skip it."""
        from django.conf import settings as dj_settings
        from .models import LivenessPersistOutbox
        from .tasks import drain_liveness_persist_outbox
        from django.db import DatabaseError
        sid = str(self._session().id)
        LivenessPersistOutbox.objects.create(
            session_id=sid, payload=self._payload(sid), attempts=1)
        capped = {**dj_settings.BIOMETRIC_LIVENESS, 'OUTBOX_MAX_ATTEMPTS': 2}
        with override_settings(BIOMETRIC_LIVENESS=capped):
            with patch('biometric_liveness.views.apply_liveness_result',
                       side_effect=DatabaseError('down')) as mock_apply:
                drain_liveness_persist_outbox.apply().get()
                row = LivenessPersistOutbox.objects.get(session_id=sid)
                self.assertEqual(row.status, 'abandoned')
                self.assertEqual(row.attempts, 2)
                # An abandoned row is excluded from subsequent sweeps.
                drain_liveness_persist_outbox.apply().get()
                self.assertEqual(mock_apply.call_count, 1)

    def test_duplicate_record_updates_single_row(self):
        """Re-recording a session's verdict updates ONE row and resets retries."""
        from .views import _record_persist_outbox
        from .models import LivenessPersistOutbox
        sid = str(self._session().id)
        payload = self._payload(sid)
        _record_persist_outbox(payload, reason='first')
        # Simulate a row that had already burned attempts / been abandoned.
        LivenessPersistOutbox.objects.filter(session_id=sid).update(
            attempts=7, status='abandoned')
        _record_persist_outbox(payload, reason='second')
        rows = LivenessPersistOutbox.objects.filter(session_id=sid)
        self.assertEqual(rows.count(), 1)
        row = rows.get()
        self.assertEqual(row.status, 'pending')
        self.assertEqual(row.attempts, 0)
        self.assertEqual(row.last_error, 'second')


class ChallengeResponseFlowTests(TestCase):
    """Gaze cognitive challenge-response is scored and gates the verdict."""

    def setUp(self):
        # Default the whole suite to "no gaze estimator loaded" so a configured
        # model in some environment cannot silently change scoring/completion
        # behaviour. Individual tests that need it override on their instance.
        cap = patch.object(GazeTrackingService, 'has_real_gaze_model', return_value=False)
        cap.start()
        self.addCleanup(cap.stop)
        self.service = LivenessSessionService()

    def _open_gaze_window(self, session):
        """Open the gaze challenge's response window now, as the first frame would."""
        gaze_ch = next(c for c in session['challenges'] if c['type'] == 'gaze')
        now_ms = LivenessSessionService._now_ms()
        session['challenge_activated_ms'][gaze_ch['sequence']] = now_ms
        return gaze_ch, now_ms

    def _stub_gaze(self, session, passed):
        """Put gaze in the fully-gating state (loaded estimator + calibrated) with
        one server-observed sample inside the window and a deterministic verdict,
        bypassing the real estimator. Enabling calibration here is what lets gaze
        contribute to the verdict (see _gaze_gates_verdict); without it gaze is
        measured but excluded."""
        from .services.gaze_tracking_service import GazePoint, TaskResult, CognitiveTaskType
        session['services']['gaze'].has_real_gaze_model = lambda: True
        self.service.config = {**self.service.config, 'GAZE_CALIBRATED': True}
        _, now_ms = self._open_gaze_window(session)
        session['gaze_track'] = [GazePoint(x=0.5, y=0.5, timestamp_ms=now_ms + 10.0,
                                           confidence=0.9, is_fixation=True)]
        score = 0.9 if passed else 0.2
        session['services']['gaze'].validate_task_response = (
            lambda *a, **k: TaskResult(
                task_type=CognitiveTaskType.FOLLOW_TARGET, is_passed=passed,
                accuracy_score=score, reaction_time_ms=100.0,
                gaze_path_similarity=score, human_likelihood_score=score))

    def _inject_pulse(self, session, n=6):
        """Give the session a real 2nd modality without processing 100+ frames."""
        from .services.pulse_oximetry_service import PulseReading
        session['pulse_readings'] = [
            PulseReading(timestamp_ms=i * 33.0, frame_number=i, rgb_means=(0.0, 0.0, 0.0),
                         ppg_value=0.0, heart_rate_bpm=72.0, heart_rate_variability=30.0,
                         spo2_estimate=None, signal_quality=0.8)
            for i in range(n)
        ]

    def _stub_pulse_score(self, score=0.95):
        """Force a deterministic (passing) pulse modality score.

        The veto tests must prove the veto flips a would-be-VERIFIED verdict, so
        the non-gaze baseline has to be genuinely above threshold. Left to the
        real rPPG scorer, the pulse score could fall short and the test would
        pass because the baseline already failed, not because the veto fired.
        complete_session scores pulse via the shared self.pulse_service.
        """
        self.service.pulse_service.get_liveness_score = lambda *a, **k: score

    def test_capabilities_gaze_unavailable_without_estimator(self):
        """Gaze must report unavailable until a real estimator is loaded.

        estimate_gaze() returns nothing without a model, so advertising it as
        available would invite the client to render an unscoreable challenge.
        """
        # Force the estimator-absent precondition so a configured model in some
        # environment cannot make this test flap.
        self.service.gaze_service.has_real_gaze_model = lambda: False
        caps = self.service.get_capabilities()
        gaze = caps['modalities']['gaze']
        self.assertFalse(gaze['available'])
        self.assertFalse(gaze['gates_verdict'])

    def test_capabilities_gaze_available_with_estimator(self):
        """With a real estimator gaze reports available; it gates only calibrated.

        The estimator measures iris position (available), but its output is not
        yet mapped to screen-target space, so it must not gate the verdict until
        calibration -- else an uncalibrated measurement could falsely veto a real
        user.
        """
        self.service.gaze_service.has_real_gaze_model = lambda: True
        # Estimator present but NOT calibrated: available, does not gate.
        self.service.config = {**self.service.config, 'GAZE_CALIBRATED': False}
        gaze = self.service.get_capabilities()['modalities']['gaze']
        self.assertTrue(gaze['available'])
        self.assertFalse(gaze['gates_verdict'])
        # Calibrated: now it gates.
        self.service.config = {**self.service.config, 'GAZE_CALIBRATED': True}
        gaze = self.service.get_capabilities()['modalities']['gaze']
        self.assertTrue(gaze['available'])
        self.assertTrue(gaze['gates_verdict'])

    def test_client_challenges_include_render_data(self):
        info = self.service.create_session(user_id=1)
        self.assertTrue(all('data' in c for c in info['challenges']))
        # The gaze challenge must actually carry what the client needs to render
        # it: a non-empty target set and the time limit. An empty {} would pass
        # the 'data' key check while leaving the UI unable to draw the challenge.
        gaze = next(c for c in info['challenges'] if c['type'] == 'gaze')
        self.assertTrue(gaze['data'].get('target_positions'))
        self.assertIn('time_limit_ms', gaze['data'])

    def test_passing_gaze_gates(self):
        info = self.service.create_session(user_id=1)
        sid = info['session_id']
        session = self.service.active_sessions[sid]
        gaze_ch = next(c for c in session['challenges'] if c['type'] == 'gaze')
        self._stub_gaze(session, passed=True)
        out = self.service.submit_challenge_response(sid, {'sequence': gaze_ch['sequence']})
        self.assertTrue(out['passed'])
        self.assertEqual(len(session['gaze_task_results']), 1)
        self._inject_pulse(session)
        result = self.service.complete_session(sid)
        self.assertIn('gaze', result.details['modalities_present'])
        self.assertIn('pulse', result.details['modalities_present'])
        self.assertNotEqual(result.verdict, 'INSUFFICIENT_SIGNAL')

    def test_failing_gaze_not_recorded(self):
        info = self.service.create_session(user_id=1)
        sid = info['session_id']
        session = self.service.active_sessions[sid]
        gaze_ch = next(c for c in session['challenges'] if c['type'] == 'gaze')
        self._stub_gaze(session, passed=False)
        out = self.service.submit_challenge_response(sid, {'sequence': gaze_ch['sequence']})
        self.assertFalse(out['passed'])
        # A failed challenge is not recorded, so it cannot count as a modality.
        self.assertEqual(len(session['gaze_task_results']), 0)
        self._inject_pulse(session)
        result = self.service.complete_session(sid)
        self.assertNotIn('gaze', result.details['modalities_present'])
        # Scored-and-failed is a positive fake signal, so it vetoes outright
        # rather than merely leaving the verdict short of signal.
        self.assertFalse(result.is_verified)
        self.assertEqual(result.verdict, 'SUSPECTED_FAKE')

    def test_failed_gaze_challenge_vetoes_verdict(self):
        """A scored-and-failed required challenge must veto, not just drop out.

        Otherwise the remaining modalities could still carry the session over
        the threshold, so the randomized challenge would not be a real gate.
        """
        info = self.service.create_session(user_id=1)
        sid = info['session_id']
        session = self.service.active_sessions[sid]
        gaze_ch = next(c for c in session['challenges'] if c['type'] == 'gaze')
        self._stub_gaze(session, passed=False)
        self.service.submit_challenge_response(sid, {'sequence': gaze_ch['sequence']})
        self.assertEqual(session['failed_required_challenges'], ['gaze'])
        # Two strong non-gaze modalities that would otherwise verify the session.
        self._inject_pulse(session)
        self._stub_pulse_score()
        session['expression_score'] = 0.95
        result = self.service.complete_session(sid)
        self.assertFalse(result.is_verified)
        self.assertEqual(result.verdict, 'SUSPECTED_FAKE')
        self.assertEqual(result.details['failed_required_challenges'], ['gaze'])

    def test_unobservable_gaze_does_not_veto(self):
        """A capability gap is an ABSENT modality, not a failed challenge.

        Gaze is gated off until a real estimator loads; treating 'no gaze
        observed' as a failure would veto every session in that state.
        """
        info = self.service.create_session(user_id=1)
        sid = info['session_id']
        session = self.service.active_sessions[sid]
        gaze_ch, _ = self._open_gaze_window(session)
        out = self.service.submit_challenge_response(sid, {'sequence': gaze_ch['sequence']})
        self.assertEqual(out['reason'], 'no_gaze_observed')
        self.assertEqual(session['failed_required_challenges'], [])
        self._inject_pulse(session)
        session['expression_score'] = 0.95
        result = self.service.complete_session(sid)
        # Not vetoed: fails/passes purely on the modalities actually present.
        self.assertNotEqual(result.verdict, 'SUSPECTED_FAKE')
        self.assertEqual(result.details['failed_required_challenges'], [])

    def test_unanswered_gaze_blocks_completion_when_measurable(self):
        """Skipping the required gaze challenge entirely must block verification.

        The failed-challenge veto only fires if gaze was attempted; a client that
        never submits it would otherwise verify on other modalities and bypass
        the randomized challenge.
        """
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        # Gaze fully gates (estimator loaded + calibrated), but the gaze challenge
        # is never answered.
        session['services']['gaze'].has_real_gaze_model = lambda: True
        self.service.config = {**self.service.config, 'GAZE_CALIBRATED': True}
        self._inject_pulse(session)
        session['expression_score'] = 0.95
        from .services.liveness_session_service import GazeChallengeIncompleteError
        # Distinct, retryable type (not a generic terminal ValueError).
        with self.assertRaises(GazeChallengeIncompleteError):
            self.service.complete_session(sid)
        # Blocked, not terminal: the session stays completable after answering.
        self.assertNotEqual(session['status'], 'completed')

    def test_unanswered_gaze_does_not_block_when_not_measurable(self):
        """Capability gap: with no estimator, skipped gaze is absent, not a skip."""
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        self._inject_pulse(session)
        session['expression_score'] = 0.95
        # has_real_gaze_model() is False by default -> must NOT raise.
        result = self.service.complete_session(sid)
        self.assertNotIn('gaze', result.details['modalities_present'])

    def test_unanswered_gaze_does_not_block_when_uncalibrated(self):
        """Estimator loaded but NOT calibrated: gaze doesn't gate, so an
        unanswered gaze challenge must not block completion (no false reject)."""
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        session['services']['gaze'].has_real_gaze_model = lambda: True
        # GAZE_CALIBRATED stays False (default) -> gaze measured but not gating.
        self._inject_pulse(session)
        session['expression_score'] = 0.95
        result = self.service.complete_session(sid)  # must NOT raise
        self.assertNotIn('gaze', result.details['modalities_present'])

    def test_pending_response_does_not_open_next_window(self):
        """A response before any frame must not open the next challenge window.

        Opening it while pending would let the window count down (and possibly
        expire) before the first observable frame ever arrives.
        """
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        self.assertEqual(session['status'], 'pending')
        expr = next(c for c in session['challenges'] if c['type'] == 'expression')
        self.service.submit_challenge_response(sid, {'sequence': expr['sequence']})
        # No frame processed yet -> no challenge window may be open.
        self.assertEqual(session['challenge_activated_ms'], {})

    def test_session_capacity_cap_rejects_new_sessions(self):
        """Past the hard cap, new sessions are refused rather than growing forever."""
        from .services.liveness_session_service import SessionCapacityError
        self.service.config = {**self.service.config, 'MAX_ACTIVE_SESSIONS': 1}
        self.service.create_session(user_id=1)
        with self.assertRaises(SessionCapacityError):
            self.service.create_session(user_id=1)

    def test_per_user_session_cap_rejects_excess(self):
        """One user cannot exhaust global capacity; a per-user live cap applies.

        The global cap protects worker memory; the per-user cap protects fairness
        so a single account cannot 503 everyone else.
        """
        from .services.liveness_session_service import SessionCapacityError
        self.service.config = {**self.service.config, 'MAX_USER_ACTIVE_SESSIONS': 2}
        self.service.create_session(user_id=1)
        self.service.create_session(user_id=1)
        with self.assertRaises(SessionCapacityError):
            self.service.create_session(user_id=1)
        # A different user is unaffected by user 1 hitting their own cap.
        self.service.create_session(user_id=2)  # must NOT raise

    def test_pulse_uses_server_timestamp_not_client(self):
        """The client frame timestamp must not define the pulse sampling clock."""
        from unittest.mock import MagicMock
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        session['services']['pulse'].process_frame = MagicMock(return_value=None)
        absurd_client_ts = -10_000_000_000.0
        self.service.process_frame(
            sid, np.zeros((64, 64, 3), np.uint8), absurd_client_ts)
        # The 2nd positional arg is the timestamp handed to the pulse service.
        called_ts = session['services']['pulse'].process_frame.call_args[0][1]
        self.assertNotEqual(called_ts, absurd_client_ts)
        self.assertGreater(called_ts, 0)  # a server epoch-ms timestamp

    def test_non_positive_configured_timeout_is_ignored(self):
        """A non-positive challenge timeout must not publish an expired gaze window."""
        self.service.config = {**self.service.config, 'COGNITIVE_TASK_TIMEOUT_MS': -5}
        info = self.service.create_session(user_id=1)
        gaze = next(c for c in info['challenges'] if c['type'] == 'gaze')
        # Falls back to the task generator's positive default, not -5.
        self.assertGreater(gaze['data']['time_limit_ms'], 0)

    def test_concurrent_create_with_stale_eviction_no_error(self):
        """Concurrent create_session (which evicts + counts active_sessions under
        _store_lock) must not raise 'dictionary changed size during iteration'."""
        import threading
        from datetime import timedelta
        from django.utils import timezone as djtz
        # Seed stale sessions so eviction actually pops entries during the burst.
        for _ in range(10):
            sid = self.service.create_session(user_id=1)['session_id']
            self.service.active_sessions[sid]['expires_at'] = (
                djtz.now() - timedelta(
                    seconds=self.service.SESSION_RETENTION_SECONDS + 60))
        n = 30
        barrier = threading.Barrier(n)
        errors = []
        lock = threading.Lock()

        def worker():
            try:
                barrier.wait()
                self.service.create_session(user_id=1)
            except Exception as exc:  # RuntimeError from the race would land here
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
            self.assertFalse(t.is_alive())
        self.assertEqual(errors, [])

    def test_retained_terminal_records_are_capped(self):
        """Terminal records are bounded by cardinality, not just age.

        Rapid create+complete must not accumulate terminal records past the cap;
        the oldest are evicted first.
        """
        self.service.config = {**self.service.config, 'MAX_RETAINED_SESSIONS': 2}
        sids = []
        for _ in range(3):
            sid = self.service.create_session(user_id=1)['session_id']
            self.service.complete_session(sid)  # -> terminal
            sids.append(sid)
        # One more create triggers eviction, which caps terminal records at 2.
        self.service.create_session(user_id=1)
        terminal = [s for s in self.service.active_sessions.values()
                    if s.get('status') in ('completed', 'expired')]
        self.assertLessEqual(len(terminal), 2)
        self.assertNotIn(sids[0], self.service.active_sessions)  # oldest evicted first

    def test_gaze_challenge_honors_configured_timeout(self):
        """COGNITIVE_TASK_TIMEOUT_MS drives the advertised AND enforced window."""
        self.service.config = {**self.service.config, 'COGNITIVE_TASK_TIMEOUT_MS': 8000}
        info = self.service.create_session(user_id=1)
        sid = info['session_id']
        gaze = next(c for c in info['challenges'] if c['type'] == 'gaze')
        self.assertEqual(gaze['data']['time_limit_ms'], 8000)
        # ...and the server-side task scored against is the same window.
        server = next(c for c in self.service.active_sessions[sid]['challenges']
                      if c['type'] == 'gaze')
        self.assertEqual(server['cognitive_task'].time_limit_ms, 8000)

    def test_discard_session_frees_slot(self):
        """discard_session removes the in-memory session (e.g. after a DB failure)."""
        sid = self.service.create_session(user_id=1)['session_id']
        self.assertIn(sid, self.service.active_sessions)
        self.service.discard_session(sid)
        self.assertNotIn(sid, self.service.active_sessions)
        self.assertNotIn(sid, self.service._session_locks)

    def test_past_deadline_pending_not_counted_as_live(self):
        """An abandoned (past-deadline) pending session must not hold a live slot."""
        from django.utils import timezone as djtz
        from datetime import timedelta
        self.service.config = {**self.service.config, 'MAX_ACTIVE_SESSIONS': 1}
        sid = self.service.create_session(user_id=1)['session_id']
        # Abandon it: past its deadline, but not yet age-evictable (< retention).
        self.service.active_sessions[sid]['expires_at'] = djtz.now() - timedelta(seconds=1)
        # A new session must still be admitted -- the abandoned one isn't live.
        self.service.create_session(user_id=1)  # must NOT raise

    def test_past_deadline_pending_counts_toward_terminal_cap(self):
        """Abandoned past-deadline sessions are bounded by the retained cap too."""
        from django.utils import timezone as djtz
        from datetime import timedelta
        self.service.config = {**self.service.config, 'MAX_RETAINED_SESSIONS': 0}
        sid = self.service.create_session(user_id=1)['session_id']
        self.service.active_sessions[sid]['expires_at'] = djtz.now() - timedelta(seconds=1)
        # Next create runs eviction; the past-deadline entry is terminal -> evicted.
        self.service.create_session(user_id=1)
        self.assertNotIn(sid, self.service.active_sessions)

    def test_capacity_cap_counts_only_live_sessions(self):
        """A completed session must not consume a capacity slot.

        Otherwise a user who churns create+complete would 503 legitimate new
        starts despite having zero in-progress sessions.
        """
        self.service.config = {**self.service.config, 'MAX_ACTIVE_SESSIONS': 1}
        sid = self.service.create_session(user_id=1)['session_id']
        self.service.complete_session(sid)  # -> terminal (INSUFFICIENT_SIGNAL)
        self.assertEqual(self.service.active_sessions[sid]['status'], 'completed')
        # The terminal record is still retained, but must not block a new start.
        self.service.create_session(user_id=1)  # must NOT raise

    def test_session_capacity_cap_holds_under_concurrency(self):
        """Under many concurrent creators the store must never exceed the cap.

        The correctness guarantee is structural (check+insert share one locked
        block), so this asserts the invariant under contention rather than trying
        to deterministically trigger the old non-atomic race (which is only
        probabilistically wrong under the GIL and cannot be forced reliably)."""
        import threading
        from .services.liveness_session_service import SessionCapacityError
        cap = 20
        self.service.config = {**self.service.config, 'MAX_ACTIVE_SESSIONS': cap}
        n_threads = 40
        barrier = threading.Barrier(n_threads)
        created = []
        errors = []
        lock = threading.Lock()

        def worker():
            try:
                barrier.wait()  # release all at once to maximize contention
                info = self.service.create_session(user_id=1)
                with lock:
                    created.append(info['session_id'])
            except SessionCapacityError:
                pass
            except Exception as exc:  # a worker crash must fail the test, not pass it
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
            self.assertFalse(t.is_alive())
        self.assertEqual(errors, [])
        # All sessions are live here, so the store size is the cap; never exceed it.
        self.assertLessEqual(len(self.service.active_sessions), cap)
        self.assertEqual(len(created), len(self.service.active_sessions))
        self.assertLessEqual(len(created), cap)

    def test_completed_session_returns_cached_verdict_not_rescored(self):
        """Re-completion is idempotent (returns the cached verdict), never a
        re-score. Anti-upgrade still holds: post-completion frames are rejected,
        so no new signal can raise the frozen verdict."""
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        self._inject_pulse(session)
        first = self.service.complete_session(sid)
        second = self.service.complete_session(sid)
        # Same frozen verdict object, not a ValueError and not a fresh scoring.
        self.assertIs(second, first)
        self.assertEqual(second.verdict, first.verdict)
        # Frames after completion are still rejected -> the verdict cannot be upgraded.
        res = self.service.process_frame(sid, np.zeros((120, 120, 3), np.uint8), 0.0)
        self.assertIn('error', res)

    def test_idempotent_completion_ignores_post_completion_signal(self):
        """Even signal stuffed in AFTER completion must not upgrade the frozen
        verdict on re-completion -- the cached result wins."""
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        first = self.service.complete_session(sid)  # no modalities -> INSUFFICIENT_SIGNAL
        self.assertEqual(first.verdict, 'INSUFFICIENT_SIGNAL')
        # Directly inject strong modalities post-completion, then re-complete.
        self._inject_pulse(session)
        session['expression_score'] = 0.95
        second = self.service.complete_session(sid)
        self.assertIs(second, first)
        self.assertEqual(second.verdict, 'INSUFFICIENT_SIGNAL')  # NOT upgraded

    def test_completed_verdict_survives_expiry(self):
        """A completed session must not be reclassified as expired and re-scored."""
        from django.utils import timezone as dj_timezone
        from datetime import timedelta
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        self._inject_pulse(session)
        first = self.service.complete_session(sid)
        # Push the deadline into the past; the terminal verdict must hold.
        session['expires_at'] = dj_timezone.now() - timedelta(seconds=1)
        res = self.service.process_frame(sid, np.zeros((120, 120, 3), np.uint8), 0.0)
        self.assertEqual(res.get('error'), 'Session already completed')
        # Completed takes precedence over expired: re-completion returns the
        # cached verdict idempotently, it is NOT reclassified/expired/re-scored.
        second = self.service.complete_session(sid)
        self.assertIs(second, first)

    def test_expired_session_cannot_be_completed(self):
        from django.utils import timezone as dj_timezone
        from datetime import timedelta
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        session['expires_at'] = dj_timezone.now() - timedelta(seconds=1)
        with self.assertRaises(ValueError):
            self.service.complete_session(sid)

    def test_challenge_replay_rejected(self):
        info = self.service.create_session(user_id=1)
        sid = info['session_id']
        session = self.service.active_sessions[sid]
        gaze_ch = next(c for c in session['challenges'] if c['type'] == 'gaze')
        # The challenge must actually be evaluated before it is consumed, so
        # give it an observable track (otherwise the first response is merely
        # premature and stays retryable -- not a replay).
        self._stub_gaze(session, passed=True)
        first = self.service.submit_challenge_response(sid, {'sequence': gaze_ch['sequence']})
        self.assertTrue(first['passed'])
        out = self.service.submit_challenge_response(sid, {'sequence': gaze_ch['sequence']})
        self.assertIn('error', out)

    def test_premature_response_does_not_consume_challenge(self):
        """An unevaluable response must stay retryable, not burn the challenge.

        Consuming it would let a client skip required gaze validation by
        submitting before the window opens.
        """
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        gaze_ch = next(c for c in session['challenges'] if c['type'] == 'gaze')
        out = self.service.submit_challenge_response(sid, {'sequence': gaze_ch['sequence']})
        self.assertEqual(out['reason'], 'challenge_not_started')
        self.assertNotIn(gaze_ch['sequence'], session['answered_challenges'])
        self.assertEqual(session['current_challenge_idx'], gaze_ch['sequence'])
        # ...and the same challenge can still be answered for real afterwards.
        self._stub_gaze(session, passed=True)
        retry = self.service.submit_challenge_response(sid, {'sequence': gaze_ch['sequence']})
        self.assertTrue(retry['passed'])

    def test_skipped_gaze_vetoes_when_gaze_is_measurable(self):
        """With gaze fully gating, letting the window lapse is a skip, not a gap."""
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        gaze_ch, _ = self._open_gaze_window(session)
        # Estimator loaded AND calibrated (gaze gates), but observe no gaze at all.
        session['services']['gaze'].has_real_gaze_model = lambda: True
        self.service.config = {**self.service.config, 'GAZE_CALIBRATED': True}
        stale = (LivenessSessionService._now_ms()
                 - gaze_ch['cognitive_task'].time_limit_ms
                 - LivenessSessionService.CHALLENGE_RESPONSE_GRACE_MS - 1000)
        session['challenge_activated_ms'][gaze_ch['sequence']] = stale
        out = self.service.submit_challenge_response(sid, {'sequence': gaze_ch['sequence']})
        self.assertEqual(out['reason'], 'challenge_window_expired')
        self.assertEqual(session['failed_required_challenges'], ['gaze'])
        self._inject_pulse(session)
        self._stub_pulse_score()
        session['expression_score'] = 0.95
        result = self.service.complete_session(sid)
        self.assertFalse(result.is_verified)
        self.assertEqual(result.verdict, 'SUSPECTED_FAKE')

    def test_client_gaze_data_is_ignored(self):
        """A client-supplied gaze track must not create a gaze modality."""
        info = self.service.create_session(user_id=1)
        sid = info['session_id']
        session = self.service.active_sessions[sid]
        gaze_ch, _ = self._open_gaze_window(session)
        # No server-observed track; client submits a forged one matching targets.
        client = [{'x': tx, 'y': ty, 'timestamp_ms': i * 40.0, 'confidence': 0.9, 'is_fixation': True}
                  for i, (tx, ty) in enumerate(gaze_ch['cognitive_task'].target_positions)]
        # Prove the forged track never even reaches scoring: validate_task_response
        # must not be called when there is no server-observed track.
        from unittest.mock import MagicMock
        session['services']['gaze'].validate_task_response = MagicMock()
        out = self.service.submit_challenge_response(
            sid, {'sequence': gaze_ch['sequence'], 'gaze_data': client})
        session['services']['gaze'].validate_task_response.assert_not_called()
        self.assertFalse(out['passed'])
        self.assertEqual(out['reason'], 'no_gaze_observed')
        self.assertEqual(len(session['gaze_task_results']), 0)  # client data ignored
        self._inject_pulse(session)
        result = self.service.complete_session(sid)
        self.assertNotIn('gaze', result.details['modalities_present'])
        self.assertEqual(result.verdict, 'INSUFFICIENT_SIGNAL')

    def test_gaze_outside_challenge_window_is_not_scored(self):
        """Samples captured after the task's time limit must not be scored."""
        from .services.gaze_tracking_service import GazePoint
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        gaze_ch, now_ms = self._open_gaze_window(session)
        limit = gaze_ch['cognitive_task'].time_limit_ms
        # Track lands entirely past the deadline (but still inside the arrival
        # grace, so the response itself is accepted and scored on nothing).
        session['gaze_track'] = [
            GazePoint(x=0.5, y=0.5, timestamp_ms=now_ms + limit + 500.0,
                      confidence=0.9, is_fixation=True)
        ]
        out = self.service.submit_challenge_response(sid, {'sequence': gaze_ch['sequence']})
        self.assertFalse(out['passed'])
        self.assertEqual(out['reason'], 'no_gaze_observed')
        self.assertEqual(len(session['gaze_task_results']), 0)

    def test_gaze_track_prunes_beyond_any_scorable_window(self):
        """Old samples are dropped, but everything a window can read survives.

        Under Redis the whole session blob is rewritten on every frame, so an
        unbounded track makes each per-frame write grow with the frame count.
        Pruning is safe only because scoring reads just the CURRENT challenge's
        [activation, activation + time_limit_ms]: retention is several windows
        wide, so nothing scorable is ever discarded.
        """
        from .services.gaze_tracking_service import GazePoint
        svc = self.service
        sid = svc.create_session(user_id=1)['session_id']
        session = svc.active_sessions[sid]
        gaze_ch, now_ms = self._open_gaze_window(session)
        retention = svc.GAZE_TRACK_RETENTION_MS
        # Well past retention, plus one the open window must still score.
        session['gaze_track'] = [
            GazePoint(x=0.1, y=0.1, timestamp_ms=now_ms - retention - 5000.0,
                      confidence=0.9, is_fixation=True),
            GazePoint(x=0.5, y=0.5, timestamp_ms=now_ms + 10.0,
                      confidence=0.9, is_fixation=True),
        ]
        fresh = GazePoint(x=0.6, y=0.6, timestamp_ms=now_ms + 20.0,
                          confidence=0.9, is_fixation=True)
        with patch.object(type(session['services']['gaze']), 'estimate_gaze',
                          return_value=fresh):
            svc.process_frame(sid, np.full((64, 64, 3), 120, dtype=np.uint8), 1.0)
        stamps = [g.timestamp_ms for g in session['gaze_track']]
        self.assertNotIn(now_ms - retention - 5000.0, stamps)   # ancient: pruned
        self.assertIn(now_ms + 10.0, stamps)                    # in-window: kept
        self.assertIn(fresh.timestamp_ms, stamps)

    def test_late_challenge_response_rejected(self):
        """A response arriving long after the window closed cannot pass.

        Gaze does NOT gate here (default: no estimator/calibration), so this also
        pins the capability-off invariant: an expired window is a capability gap,
        not a skip, and must not veto -- do NOT call _stub_gaze, which would turn
        gaze into a fully-gating modality and flip the expired window to a veto.
        """
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        gaze_ch = next(c for c in session['challenges'] if c['type'] == 'gaze')
        # Backdate activation so the window (plus arrival grace) has closed.
        stale = (LivenessSessionService._now_ms()
                 - gaze_ch['cognitive_task'].time_limit_ms
                 - LivenessSessionService.CHALLENGE_RESPONSE_GRACE_MS - 1000)
        session['challenge_activated_ms'][gaze_ch['sequence']] = stale
        out = self.service.submit_challenge_response(sid, {'sequence': gaze_ch['sequence']})
        self.assertFalse(out['passed'])
        self.assertEqual(out['reason'], 'challenge_window_expired')
        self.assertEqual(len(session['gaze_task_results']), 0)
        # Gaze does not gate the verdict here, so an expired window is a
        # capability gap, not a skip: it must not veto. Vetoing when gaze does
        # not gate would fail every session in that state.
        self.assertEqual(session['failed_required_challenges'], [])

    def test_unstarted_challenge_cannot_pass(self):
        """With no window opened (no frames observed), gaze cannot be scored."""
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        gaze_ch = next(c for c in session['challenges'] if c['type'] == 'gaze')
        out = self.service.submit_challenge_response(sid, {'sequence': gaze_ch['sequence']})
        self.assertFalse(out['passed'])
        self.assertEqual(out['reason'], 'challenge_not_started')

    def test_out_of_order_answer_keeps_index_on_unanswered(self):
        """Answering a later challenge first must not skip an earlier one."""
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        sequences = sorted(c['sequence'] for c in session['challenges'])
        first, second = sequences[0], sequences[1]
        # `second` is the expression challenge, which is acknowledged (and thus
        # consumed) immediately; if it were NOT consumed the sequencing assertion
        # below could pass vacuously, so pin the consumption explicitly.
        self.service.submit_challenge_response(sid, {'sequence': second})
        self.assertIn(second, session['answered_challenges'])
        self.assertEqual(session['current_challenge_idx'], first)
        # Omitting 'sequence' must target the still-unanswered challenge.
        out = self.service.submit_challenge_response(sid, {})
        self.assertNotIn('error', out)
        self.assertEqual(out['sequence'], first)

    def test_stale_sessions_are_evicted(self):
        """The in-memory store must not grow for the process lifetime."""
        from django.utils import timezone as dj_timezone
        from datetime import timedelta
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        session['expires_at'] = dj_timezone.now() - timedelta(
            seconds=LivenessSessionService.SESSION_RETENTION_SECONDS + 60)
        self.service.create_session(user_id=1)  # eviction runs on create
        self.assertNotIn(sid, self.service.active_sessions)
        self.assertNotIn(sid, self.service._session_locks)

    def test_recent_terminal_session_is_retained(self):
        """A just-completed session stays retained; re-completion is idempotent."""
        sid = self.service.create_session(user_id=1)['session_id']
        first = self.service.complete_session(sid)
        self.service.create_session(user_id=1)
        self.assertIn(sid, self.service.active_sessions)
        # Retained terminal record: re-completion returns the cached verdict, not
        # a re-score (and not an error).
        self.assertIs(self.service.complete_session(sid), first)

    def test_no_response_fails_closed(self):
        sid = self.service.create_session(user_id=1)['session_id']
        result = self.service.complete_session(sid)
        self.assertEqual(result.verdict, 'INSUFFICIENT_SIGNAL')
        self.assertFalse(result.is_verified)

    def test_unknown_session_returns_error(self):
        out = self.service.submit_challenge_response('does-not-exist', {'gaze_data': []})
        self.assertIn('error', out)

    def test_non_dict_response_does_not_crash(self):
        # An explicit null / non-object 'response' must be normalized, not raise.
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        out = self.service.submit_challenge_response(sid, None)
        self.assertIn('next_challenge', out)
        # ...and malformed input must not consume the required challenge.
        self.assertEqual(session['answered_challenges'], set())


class HardwareSpo2RelayTests(TestCase):
    """A client-paired BLE oximeter relays real SpO2 into scoring; it is never
    fabricated from the webcam, is server-clock stamped, and is capability-gated."""

    def setUp(self):
        """Default to no gaze estimator so scoring/completion stay deterministic."""
        cap = patch.object(GazeTrackingService, 'has_real_gaze_model', return_value=False)
        cap.start()
        self.addCleanup(cap.stop)
        self.service = LivenessSessionService()

    def _session(self):
        """Create a session and return (session_id, session dict)."""
        sid = self.service.create_session(user_id=1)['session_id']
        return sid, self.service.active_sessions[sid]

    def test_relayed_spo2_is_ingested_and_fresh(self):
        """A relayed reading is stored and reads back fresh at a later frame time."""
        sid, session = self._session()
        out = self.service.submit_hardware_spo2(sid, 98.0, 0.9)
        self.assertTrue(out['accepted'])
        pulse = session['services']['pulse']
        self.assertTrue(pulse.has_hardware_spo2())
        # Fresh reading surfaces when read at a slightly-later frame time.
        self.assertEqual(
            pulse._current_hardware_spo2(LivenessSessionService._now_ms()), 98.0)

    def test_relayed_spo2_surfaces_on_the_pulse_reading(self):
        """The reading appears on the PulseReading even during the rPPG warm-up."""
        # Even during the rPPG warm-up (buffer < 3s), the external reading shows.
        sid, session = self._session()
        self.service.submit_hardware_spo2(sid, 97.0, 0.9)
        pulse = session['services']['pulse']
        frame = np.full((120, 120, 3), 128, dtype=np.uint8)
        reading = pulse.process_frame(frame, LivenessSessionService._now_ms(), None)
        self.assertEqual(reading.spo2_estimate, 97.0)

    def test_spo2_is_stamped_on_the_server_clock_not_the_client(self):
        """The stored timestamp is the server clock; no client timestamp is accepted."""
        # A client cannot keep a stale reading "fresh" by lying about its time.
        sid, session = self._session()
        before = LivenessSessionService._now_ms()
        self.service.submit_hardware_spo2(sid, 96.0, 0.9)
        ts = session['services']['pulse'].hardware_spo2_timestamp_ms
        self.assertIsNotNone(ts)
        self.assertGreaterEqual(ts, before)
        self.assertLessEqual(ts, LivenessSessionService._now_ms())

    def test_out_of_range_spo2_is_rejected_not_clamped(self):
        """An impossible SpO2 (>100) is rejected outright, not clamped into range."""
        sid, session = self._session()
        out = self.service.submit_hardware_spo2(sid, 150.0, 0.9)
        self.assertFalse(out['accepted'])
        self.assertFalse(session['services']['pulse'].has_hardware_spo2())

    def test_below_threshold_quality_reading_is_not_accepted(self):
        """`accepted` reflects the read path (quality/freshness), not just storage:
        a reading below MIN_SPO2_QUALITY is stored but can never surface/gate, so
        accepted must be False rather than claim otherwise."""
        sid, session = self._session()
        out = self.service.submit_hardware_spo2(sid, 98.0, 0.1)  # quality < 0.3 floor
        self.assertFalse(out['accepted'])
        # It IS stored (range/finiteness valid) -- the quality gate excludes it.
        self.assertTrue(session['services']['pulse'].has_hardware_spo2())

    def test_none_clears_a_prior_reading(self):
        """Relaying None (device disconnect) clears a previously stored reading."""
        sid, session = self._session()
        self.service.submit_hardware_spo2(sid, 98.0, 0.9)
        out = self.service.submit_hardware_spo2(sid, None)
        self.assertFalse(out['accepted'])
        self.assertFalse(session['services']['pulse'].has_hardware_spo2())

    def test_non_numeric_spo2_is_rejected(self):
        """A non-numeric SpO2 payload is coerced to None and rejected, not crashed."""
        sid, _ = self._session()
        out = self.service.submit_hardware_spo2(sid, 'not-a-number', 0.9)
        self.assertFalse(out['accepted'])

    def test_completed_session_rejects_spo2(self):
        """A completed session rejects late SpO2 with a state-conflict marker."""
        sid, session = self._session()
        session['status'] = 'completed'
        out = self.service.submit_hardware_spo2(sid, 98.0, 0.9)
        self.assertIn('error', out)
        self.assertTrue(out.get('state_conflict'))

    def test_unknown_session_rejects_spo2(self):
        """An unknown session id is rejected with 'Session not found'."""
        out = self.service.submit_hardware_spo2('no-such-session', 98.0, 0.9)
        self.assertEqual(out.get('error'), 'Session not found')
        self.assertTrue(out.get('state_conflict'))

    def test_spo2_capability_reports_external_hardware_only(self):
        """Capabilities report SpO2 as external-hardware-only (server never measures it)."""
        caps = self.service.get_capabilities()
        spo2 = caps['modalities']['spo2']
        self.assertFalse(spo2['available'])  # server never measures it
        self.assertEqual(spo2['requires'], 'ble_pulse_oximeter')

    def test_healthy_spo2_raises_and_abnormal_lowers_the_pulse_score(self):
        """A present SpO2 actually MOVES the pulse liveness score -- higher when
        healthy, lower when abnormal -- proving it gates the verdict, not just
        displays. When absent it is excluded (not neutral-filled)."""
        from .services.pulse_oximetry_service import PulseReading
        pulse = PulseOximetryService()

        def readings(spo2):
            # Identical HR (72) -> hr_range 1.0 but hr_variability 0.5, so the
            # SpO2 component actually shifts the averaged consistency score.
            return [
                PulseReading(timestamp_ms=i * 33.0, frame_number=i,
                             rgb_means=(0.0, 0.0, 0.0), ppg_value=0.0,
                             heart_rate_bpm=72.0, heart_rate_variability=30.0,
                             spo2_estimate=spo2, signal_quality=0.8)
                for i in range(10)
            ]

        score_none = pulse.get_liveness_score(readings(None))
        score_healthy = pulse.get_liveness_score(readings(98.0))
        score_abnormal = pulse.get_liveness_score(readings(80.0))
        self.assertGreater(score_healthy, score_none)
        self.assertLess(score_abnormal, score_none)


class RppgSpo2HonestyTests(TestCase):
    """SpO2 is never derived from a webcam (removes the 110-25*R fabrication)."""

    def test_rppg_never_fabricates_spo2(self):
        """The rPPG extractor returns no SpO2, even with a full RGB buffer."""
        extractor = RPPGExtractor()
        # Even with a full RGB buffer, no SpO2 is invented from the webcam.
        for _ in range(extractor.fps * 4):
            extractor.process_frame(np.full((120, 120, 3), 150, dtype=np.uint8))
        self.assertEqual(extractor._calculate_spo2(), (None, 0.0))
        result = extractor.process_frame(np.full((120, 120, 3), 150, dtype=np.uint8))
        self.assertIsNone(result.get('spo2'))


class _FakeRedis:
    """
    Minimal in-process Redis double for the session-store tests.

    Implements only what RedisSessionStore uses (set with nx/px/ex, get, delete,
    exists, pexpire, sadd/srem/scard/smembers, and the ZSET commands backing the
    live indexes), returning bytes like a real from_url() client so the store's
    decode paths are exercised. Key TTL is not simulated -- the tests are
    hermetic and assert state sharing/locking, not expiry timing. ZSET SCORES
    are modelled faithfully, because the capacity count depends on them.
    """

    def __init__(self):
        self.kv = {}
        self.sets = {}
        self.zsets = {}

    @staticmethod
    def _b(v):
        return v if isinstance(v, bytes) else str(v).encode('utf-8')

    def set(self, name, value, nx=False, px=None, ex=None, keepttl=False):
        if nx and name in self.kv:
            return None
        self.kv[name] = self._b(value)
        return True

    def get(self, name):
        return self.kv.get(name)

    def delete(self, *names):
        removed = 0
        for name in names:
            removed += self.kv.pop(name, None) is not None
            removed += self.sets.pop(name, None) is not None
            removed += self.zsets.pop(name, None) is not None
        return removed

    # -- ZSET (live indexes, scored by session deadline) ------------------- #

    def zadd(self, name, mapping):
        z = self.zsets.setdefault(name, {})
        added = 0
        for member, score in mapping.items():
            b = self._b(member)
            if b not in z:
                added += 1
            z[b] = float(score)
        return added

    def zrem(self, name, *members):
        z = self.zsets.get(name, {})
        return sum(z.pop(self._b(m), None) is not None for m in members)

    def zcard(self, name):
        return len(self.zsets.get(name, {}))

    def zremrangebyscore(self, name, minimum, maximum):
        z = self.zsets.get(name, {})
        lo = float('-inf') if minimum in ('-inf', b'-inf') else float(minimum)
        hi = float('inf') if maximum in ('+inf', b'+inf') else float(maximum)
        doomed = [m for m, s in z.items() if lo <= s <= hi]
        for m in doomed:
            del z[m]
        return len(doomed)

    def exists(self, name):
        return 1 if name in self.kv else 0

    def pexpire(self, name, ms):
        return True

    def expire(self, name, seconds, nx=False, xx=False, gt=False, lt=False):
        # TTL is not modelled here (see the class note); accept the Redis 7+
        # EXPIRE NX kwargs so the terminal-save backfill path runs unchanged.
        return 1 if name in self.kv else 0

    def sadd(self, name, *vals):
        s = self.sets.setdefault(name, set())
        added = 0
        for v in vals:
            b = self._b(v)
            if b not in s:
                s.add(b)
                added += 1
        return added

    def srem(self, name, *vals):
        s = self.sets.get(name, set())
        removed = 0
        for v in vals:
            b = self._b(v)
            if b in s:
                s.discard(b)
                removed += 1
        return removed

    def scard(self, name):
        return len(self.sets.get(name, set()))

    def smembers(self, name):
        return set(self.sets.get(name, set()))

    def pipeline(self):
        return _FakePipeline(self)

    def register_script(self, script):
        """
        Emulate the two lock scripts the store registers.

        There is no Lua interpreter here, so we match on the exact source the
        store registers and implement the same semantics in Python. Matching on
        identity (rather than reimplementing "some CAS") keeps the double honest:
        adding a third script fails loudly instead of silently no-op'ing.
        """
        from .services.session_store import _RELEASE_LUA, _RENEW_LUA

        if script == _RELEASE_LUA:
            def release(keys, args):
                key, token = keys[0], self._b(args[0])
                if self.kv.get(key) == token:
                    return self.delete(key)
                return 0
            return release

        if script == _RENEW_LUA:
            def renew(keys, args):
                key, token = keys[0], self._b(args[0])
                # TTL is not modelled (see the class note), so a renew of a key
                # we still own simply succeeds.
                return 1 if self.kv.get(key) == token else 0
            return renew

        raise AssertionError(f'_FakeRedis has no emulation for script: {script!r}')


class _FakePipeline:
    """Queues calls and executes them in order (matches redis-py's pipeline use
    in count_live: buffered EXISTS then execute())."""

    def __init__(self, client):
        self._client = client
        self._queue = []

    def exists(self, name):
        self._queue.append(('exists', (name,)))
        return self

    def execute(self):
        return [getattr(self._client, op)(*args) for op, args in self._queue]


def _redis_service(fake, retention=420):
    """A LivenessSessionService wired to a shared fake-Redis store."""
    from .services.liveness_session_service import LivenessSessionService
    from .services.session_store import RedisSessionStore
    svc = LivenessSessionService()
    svc._redis_store = RedisSessionStore(fake, svc._new_session_services, retention)
    return svc


class SessionStoreBackendSelectionTests(TestCase):
    """An explicitly requested Redis backend must never degrade silently."""

    def test_misconfigured_redis_backend_fails_fast(self):
        """SESSION_STORE='redis' + an unusable client raises instead of falling
        back to the per-worker dict (which would reintroduce the cross-process
        bug the backend exists to fix, with only a log line as evidence)."""
        from django.core.exceptions import ImproperlyConfigured
        from django.conf import settings as dj_settings
        from .services.liveness_session_service import LivenessSessionService
        cfg = {**dj_settings.BIOMETRIC_LIVENESS, 'SESSION_STORE': 'redis'}
        with override_settings(BIOMETRIC_LIVENESS=cfg):
            with patch('redis.Redis.from_url', side_effect=ValueError('bad url')):
                with self.assertRaises(ImproperlyConfigured):
                    LivenessSessionService()

    def test_memory_backend_is_the_default(self):
        """Unconfigured (or 'memory') keeps the in-memory store -- no Redis."""
        from .services.liveness_session_service import LivenessSessionService
        self.assertIsNone(LivenessSessionService()._redis_store)

    def test_session_url_keeps_its_own_db_when_derived_from_redis_url(self):
        """Deriving from a shared REDIS_URL must still pin the liveness database:
        sharing the cache's db exposes in-flight sessions to its FLUSHDB and its
        eviction policy, which would drop live verifications."""
        from password_manager.settings.base import _liveness_session_redis_url
        with patch.dict(os.environ, {'REDIS_URL': 'redis://cache-host:6379/0'},
                        clear=False):
            os.environ.pop('LIVENESS_SESSION_REDIS_URL', None)
            self.assertEqual(_liveness_session_redis_url(),
                             'redis://cache-host:6379/3')

    def test_explicit_session_url_wins(self):
        from password_manager.settings.base import _liveness_session_redis_url
        with patch.dict(os.environ, {
            'REDIS_URL': 'redis://cache-host:6379/0',
            'LIVENESS_SESSION_REDIS_URL': 'rediss://liveness-host:6380/7',
        }, clear=False):
            self.assertEqual(_liveness_session_redis_url(),
                             'rediss://liveness-host:6380/7')


class SessionStoreSerializationTests(TestCase):
    """serialize/deserialize must round-trip every non-trivial session field."""

    def test_round_trip_preserves_state(self):
        from .services.session_store import serialize_session, deserialize_session
        from .services.liveness_session_service import LivenessSessionService
        from .services.gaze_tracking_service import GazePoint, TaskResult, CognitiveTaskType
        from .services.pulse_oximetry_service import PulseReading
        svc = LivenessSessionService()
        info = svc.create_session(user_id=7, context='login')
        sid = info['session_id']
        session = svc.active_sessions[sid]
        # Populate representative accumulator state across every serialized type.
        session['frames_processed'] = 12
        session['status'] = 'in_progress'
        session['answered_challenges'] = {0, 2}
        session['challenge_activated_ms'] = {0: 111.0, 1: 222.0}
        session['failed_required_challenges'] = ['gaze']
        session['pulse_readings'] = [PulseReading(
            timestamp_ms=1.0, frame_number=1, rgb_means=(1.0, 2.0, 3.0),
            ppg_value=0.5, heart_rate_bpm=72.0, heart_rate_variability=5.0,
            spo2_estimate=98.0, signal_quality=0.9)]
        session['gaze_track'] = [GazePoint(x=0.5, y=0.5, timestamp_ms=10.0,
                                           confidence=0.8, is_fixation=True)]
        session['gaze_task_results'] = [TaskResult(
            task_type=CognitiveTaskType.FOLLOW_TARGET, is_passed=True,
            accuracy_score=0.8, reaction_time_ms=300.0,
            gaze_path_similarity=0.7, human_likelihood_score=0.9)]
        session['deepfake_probs'] = [0.1, 0.2]
        session['expression_score'] = 0.66

        blob = serialize_session(session)
        restored = deserialize_session(blob, svc._new_session_services)

        self.assertEqual(restored['frames_processed'], 12)
        self.assertEqual(restored['status'], 'in_progress')
        # A set survives as a set (the replay guard depends on membership).
        self.assertEqual(restored['answered_challenges'], {0, 2})
        # challenge_activated_ms keys must come back as ints, not JSON strings.
        self.assertEqual(restored['challenge_activated_ms'], {0: 111.0, 1: 222.0})
        self.assertEqual(restored['failed_required_challenges'], ['gaze'])
        self.assertEqual(restored['pulse_readings'][0].heart_rate_bpm, 72.0)
        self.assertEqual(restored['gaze_track'][0].x, 0.5)
        self.assertTrue(restored['gaze_task_results'][0].is_passed)
        self.assertEqual(restored['expression_score'], 0.66)
        # The randomized cognitive task survives so scoring stays reproducible.
        gaze_ch = next(c for c in restored['challenges'] if c['type'] == 'gaze')
        self.assertIsNotNone(gaze_ch['cognitive_task'])
        self.assertEqual(gaze_ch['cognitive_task'].task_type,
                         CognitiveTaskType.FOLLOW_TARGET)

    def test_pulse_buffers_survive_round_trip(self):
        """The rPPG accumulator (the actual pulse signal) must survive a hand-off."""
        from .services.session_store import serialize_session, deserialize_session
        from .services.liveness_session_service import LivenessSessionService
        svc = LivenessSessionService()
        info = svc.create_session(user_id=1)
        sid = info['session_id']
        session = svc.active_sessions[sid]
        pulse = session['services']['pulse']
        for i in range(20):
            pulse.process_frame(np.full((64, 64, 3), 120, dtype=np.uint8), float(i))
        depth = len(pulse.rgb_buffer)
        self.assertGreater(depth, 0)
        restored = deserialize_session(serialize_session(session),
                                       svc._new_session_services)
        self.assertEqual(len(restored['services']['pulse'].rgb_buffer), depth)


class RedisSessionStoreCrossProcessTests(TestCase):
    """The core claim: a session created by one worker is usable by another."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='xproc', email='x@example.com', password='pw')
        self.fake = _FakeRedis()
        # Two INDEPENDENT service instances over the SAME shared Redis -- stand-ins
        # for the REST worker and the WS worker (different processes/replicas).
        self.rest = _redis_service(self.fake)
        self.ws = _redis_service(self.fake)

    def _frame(self):
        return np.full((64, 64, 3), 120, dtype=np.uint8)

    def test_session_created_on_one_instance_is_processable_on_another(self):
        info = self.rest.create_session(user_id=self.user.id)
        sid = info['session_id']
        # The WS instance -- which never saw create_session -- finds it and the
        # frame counter accumulates ACROSS the process boundary.
        r1 = self.ws.process_frame(sid, self._frame(), 1.0)
        self.assertEqual(r1['frame_number'], 1)
        r2 = self.rest.process_frame(sid, self._frame(), 2.0)
        self.assertEqual(r2['frame_number'], 2)
        self.assertNotIn(sid, self.rest._sessions_mem)  # nothing kept in-process

    def test_replay_guard_survives_across_instances(self):
        info = self.rest.create_session(user_id=self.user.id)
        sid = info['session_id']
        # Answer the expression challenge (seq 1) on the WS instance.
        self.ws.process_frame(sid, self._frame(), 1.0)
        first = self.ws.submit_challenge_response(sid, {'sequence': 1})
        self.assertNotIn('error', first)
        # The REST instance must see it as already answered (shared set).
        again = self.rest.submit_challenge_response(sid, {'sequence': 1})
        self.assertEqual(again.get('error'), 'Challenge already answered')

    def test_completion_is_idempotent_across_instances(self):
        info = self.rest.create_session(user_id=self.user.id)
        sid = info['session_id']
        for i in range(3):
            self.ws.process_frame(sid, self._frame(), float(i))
        first = self.rest.complete_session(sid)
        # The WS instance re-completing returns the SAME frozen verdict, not a
        # re-score or a state error (idempotent completion across processes).
        second = self.ws.complete_session(sid)
        self.assertEqual(first.verdict, second.verdict)
        self.assertEqual(first.is_verified, second.is_verified)
        self.assertEqual(first.overall_liveness_score, second.overall_liveness_score)

    def test_lock_is_released_after_an_exception(self):
        missing = 'does-not-exist'
        with self.assertRaises(ValueError):
            self.rest.complete_session(missing)
        # The per-session lock must have been released in the finally, so a new
        # caller can still acquire it (no leaked lock on the error path).
        self.assertTrue(self.rest._redis_store.acquire(missing))

    def test_capacity_counts_shared_live_sessions(self):
        # A tiny global cap enforced across BOTH instances via the shared index.
        from .services.liveness_session_service import SessionCapacityError
        for s in (self.rest, self.ws):
            s.config = {**s.config, 'MAX_ACTIVE_SESSIONS': 2}
        self.rest.create_session(user_id=self.user.id)
        self.ws.create_session(user_id=self.user.id)
        with self.assertRaises(SessionCapacityError):
            self.rest.create_session(user_id=self.user.id)

    def test_abandoned_session_stops_counting_against_capacity(self):
        """An abandoned session must free its slot at its DEADLINE, not at the
        end of the retention window.

        Nothing saves an abandoned session again, so it never leaves the live
        index by the normal route. Counting it while its blob is merely retained
        would lock the user out of new verifications for minutes -- the
        in-memory backend never did that, because it counts with _is_live().
        """
        from datetime import timedelta
        from django.utils import timezone
        from .services.liveness_session_service import SessionCapacityError
        for s in (self.rest, self.ws):
            s.config = {**s.config, 'MAX_USER_ACTIVE_SESSIONS': 1}
        self.rest.create_session(user_id=self.user.id)
        # Slot is held while the session is genuinely live.
        with self.assertRaises(SessionCapacityError):
            self.ws.create_session(user_id=self.user.id)
        # Abandoned: the client never calls again, so nothing re-indexes it --
        # only the clock moves. Advance past the session timeout (120s).
        later = timezone.now() + timedelta(seconds=300)
        with patch('django.utils.timezone.now', return_value=later):
            self.assertIsNotNone(self.ws.create_session(user_id=self.user.id))

    def test_discard_frees_a_capacity_slot_cross_instance(self):
        from .services.liveness_session_service import SessionCapacityError
        for s in (self.rest, self.ws):
            s.config = {**s.config, 'MAX_ACTIVE_SESSIONS': 1}
        info = self.rest.create_session(user_id=self.user.id)
        with self.assertRaises(SessionCapacityError):
            self.ws.create_session(user_id=self.user.id)
        self.ws.discard_session(info['session_id'])  # freed on the other instance
        self.assertIsNotNone(self.ws.create_session(user_id=self.user.id))

    def test_lock_contention_raises_session_lock_error(self):
        """When another worker holds the per-session lock, a mutating call fails
        with the retryable SessionLockError rather than mutating concurrently."""
        from .services.liveness_session_service import SessionLockError
        from .services.session_store import RedisSessionStore
        info = self.rest.create_session(user_id=self.user.id)
        sid = info['session_id']
        # A different holder already owns the lock; the fake set(nx=True) refuses.
        self.fake.set(RedisSessionStore._LOCK + sid, 'other-worker', nx=True, px=15000)
        # Skip the real 3s spin -- we only assert the give-up behaviour.
        with patch('time.sleep', lambda *_a, **_k: None):
            with self.assertRaises(SessionLockError):
                self.rest.process_frame(sid, self._frame(), 1.0)

    def test_release_never_deletes_another_workers_lock(self):
        """The release is a server-side compare-and-delete, so a holder whose
        lease already expired and was re-acquired elsewhere cannot delete the
        NEW owner's lock (which would let a third worker in concurrently)."""
        from .services.session_store import RedisSessionStore
        store = self.rest._redis_store
        sid = 'lease-handover'
        key = RedisSessionStore._LOCK + sid
        self.assertTrue(store.acquire(sid))
        # Simulate the lease expiring and another worker taking the lock.
        self.fake.kv[key] = b'other-worker'
        store.release(sid)
        self.assertEqual(self.fake.kv.get(key), b'other-worker')

    def test_save_is_fenced_on_still_holding_the_lease(self):
        """If the lease is lost mid-operation, the worker's now-stale copy must
        NOT be written over whichever worker owns the session -- the call fails
        retryably instead of silently losing the other worker's frames."""
        from .services.liveness_session_service import SessionLockError
        info = self.rest.create_session(user_id=self.user.id)
        sid = info['session_id']
        self.ws.process_frame(sid, self._frame(), 1.0)  # the state to protect
        with patch.object(type(self.rest._redis_store), 'renew', return_value=False):
            with self.assertRaises(SessionLockError):
                self.rest.process_frame(sid, self._frame(), 2.0)
        # The other worker's frame count survived; ours was discarded.
        self.assertEqual(self.ws.get_session_status(sid)['frames_processed'], 1)

    def test_status_is_read_without_rebuilding_the_session(self):
        """The polled status endpoint takes the metadata-only path: same answer,
        no deserialize_session/detector construction."""
        info = self.rest.create_session(user_id=self.user.id)
        sid = info['session_id']
        self.ws.process_frame(sid, self._frame(), 1.0)
        with patch.object(type(self.rest._redis_store), 'load') as load:
            status_payload = self.rest.get_session_status(sid)
        load.assert_not_called()
        self.assertEqual(status_payload['frames_processed'], 1)
        self.assertEqual(status_payload['status'], 'in_progress')
        self.assertFalse(status_payload['is_expired'])

    def test_status_of_missing_session_is_none(self):
        self.assertIsNone(self.rest.get_session_status('does-not-exist'))

    def test_completion_with_real_scores_persists_over_redis(self):
        """A completed verdict carrying real modality scores must serialize.

        gaze/pulse get_liveness_score derive from np.mean -> np.float64; if that
        leaks into SessionResult, json.dumps raises inside _run_locked_redis's
        save and the most important write (the frozen verdict) is lost with a
        500. This seeds real gaze+pulse signal (the 3-frame cross-process test
        yields an empty INSUFFICIENT_SIGNAL, so it never exercised this) and
        asserts completion persists and reads back identically on the other
        instance.
        """
        from .services.gaze_tracking_service import TaskResult, CognitiveTaskType
        from .services.pulse_oximetry_service import PulseReading
        info = self.rest.create_session(user_id=self.user.id)
        sid = info['session_id']
        session = self.rest._redis_store.load(sid)
        session['gaze_task_results'] = [TaskResult(
            task_type=CognitiveTaskType.FOLLOW_TARGET, is_passed=True,
            accuracy_score=0.9, reaction_time_ms=100.0,
            gaze_path_similarity=0.8, human_likelihood_score=0.9)]
        session['pulse_readings'] = [PulseReading(
            timestamp_ms=i * 33.0, frame_number=i, rgb_means=(0., 0., 0.),
            ppg_value=0.0, heart_rate_bpm=72.0, heart_rate_variability=30.0,
            spo2_estimate=None, signal_quality=0.8) for i in range(6)]
        self.rest._redis_store.save(sid, session)
        result = self.rest.complete_session(sid)  # must not raise on serialize
        self.assertIn('gaze', result.details['modalities_present'])
        self.assertIn('pulse', result.details['modalities_present'])
        # The frozen verdict round-trips to the other instance (proof it saved).
        reread = self.ws.complete_session(sid)
        self.assertEqual(reread.overall_liveness_score, result.overall_liveness_score)
        self.assertEqual(reread.verdict, result.verdict)


class GazeEstimatorGeometryTests(TestCase):
    """_gaze_from_landmarks is a real iris-in-socket measurement, not a stub."""

    def _face(self, iris_a=(0.35, 0.375), iris_b=(0.65, 0.375), open_=True):
        from .services.gaze_tracking_service import GazeTrackingService as G
        lm = np.zeros((478, 3), dtype=np.float64)
        bot = 0.40 if open_ else 0.375
        # Eye A socket + iris
        lm[G._EYE_A['corner1']] = [0.30, 0.375, 0]
        lm[G._EYE_A['corner2']] = [0.40, 0.375, 0]
        lm[G._EYE_A['top']] = [0.35, 0.35 if open_ else 0.375, 0]
        lm[G._EYE_A['bottom']] = [0.35, bot, 0]
        lm[G._EYE_A['iris']] = [iris_a[0], iris_a[1], 0]
        # Eye B socket + iris
        lm[G._EYE_B['corner1']] = [0.60, 0.375, 0]
        lm[G._EYE_B['corner2']] = [0.70, 0.375, 0]
        lm[G._EYE_B['top']] = [0.65, 0.35 if open_ else 0.375, 0]
        lm[G._EYE_B['bottom']] = [0.65, bot, 0]
        lm[G._EYE_B['iris']] = [iris_b[0], iris_b[1], 0]
        return lm

    def test_centered_iris_maps_to_center(self):
        from .services.gaze_tracking_service import GazeTrackingService as G
        gaze = G._gaze_from_landmarks(self._face())
        self.assertIsNotNone(gaze)
        x, y, conf = gaze
        self.assertAlmostEqual(x, 0.5, places=2)
        self.assertAlmostEqual(y, 0.5, places=2)
        self.assertGreater(conf, 0.5)

    def test_iris_shift_moves_gaze(self):
        from .services.gaze_tracking_service import GazeTrackingService as G
        left = G._gaze_from_landmarks(self._face(iris_a=(0.31, 0.375), iris_b=(0.61, 0.375)))
        right = G._gaze_from_landmarks(self._face(iris_a=(0.39, 0.375), iris_b=(0.69, 0.375)))
        self.assertLess(left[0], 0.3)   # iris toward inner corners -> low x
        self.assertGreater(right[0], 0.7)

    def test_closed_eye_is_not_measurable(self):
        from .services.gaze_tracking_service import GazeTrackingService as G
        self.assertIsNone(G._gaze_from_landmarks(self._face(open_=False)))

    def test_too_few_landmarks_returns_none(self):
        from .services.gaze_tracking_service import GazeTrackingService as G
        self.assertIsNone(G._gaze_from_landmarks(np.zeros((468, 3))))

    def test_estimate_gaze_none_without_model(self):
        """No model loaded => estimate_gaze reports nothing (never fabricates).

        Patches the CAPABILITY predicate, not the cached _gaze_model: estimate_gaze
        calls _init_gaze_model, which re-resolves the class attribute from
        get_face_landmarker() -- so patching the cache alone would flap in an
        environment where a FaceLandmarker asset is actually provisioned.
        """
        from .services.gaze_tracking_service import GazeTrackingService
        g = GazeTrackingService()
        with patch.object(GazeTrackingService, 'has_real_gaze_model',
                          return_value=False):
            self.assertIsNone(g.estimate_gaze(self._face(), self._face()))

    def test_reaction_time_from_challenge_start(self):
        """With a challenge onset provided, reaction_time is a real latency."""
        from .services.gaze_tracking_service import (
            GazeTrackingService, CognitiveTask, CognitiveTaskType, GazePoint)
        g = GazeTrackingService()
        task = CognitiveTask(
            task_type=CognitiveTaskType.FOLLOW_TARGET, instruction='x',
            target_positions=[(0.5, 0.5)], time_limit_ms=5000, expected_sequence=[0])
        pts = [GazePoint(x=0.5, y=0.5, timestamp_ms=1000.0 + i * 40.0,
                         confidence=0.9, is_fixation=True) for i in range(6)]
        res = g.validate_task_response(task, pts, challenge_start_ms=900.0)
        # First on-target sample is at 1000ms, onset 900ms -> 100ms latency.
        self.assertAlmostEqual(res.reaction_time_ms, 100.0, places=1)

    def test_accuracy_dedupes_overlapping_targets(self):
        """One gaze sample must not satisfy multiple overlapping targets."""
        from .services.gaze_tracking_service import (
            GazeTrackingService, CognitiveTask, CognitiveTaskType, GazePoint)
        g = GazeTrackingService()
        # Two identical targets, a single on-point gaze sample.
        task = CognitiveTask(
            task_type=CognitiveTaskType.FOLLOW_TARGET, instruction='x',
            target_positions=[(0.5, 0.5), (0.5, 0.5)], time_limit_ms=5000,
            expected_sequence=[0, 1])
        one = [GazePoint(x=0.5, y=0.5, timestamp_ms=0.0, confidence=0.9, is_fixation=True)]
        # Only one target can be credited by the single sample -> 0.5, not 1.0.
        self.assertEqual(g._calculate_gaze_accuracy(task, one), 0.5)


class ActionUnitGeometryTests(TestCase):
    """AU intensities are real landmark geometry (deterministic), not random."""

    def setUp(self):
        self.analyzer = MicroExpressionAnalyzer()

    def _neutral(self):
        from .services.micro_expression_analyzer import MicroExpressionAnalyzer as M
        lm = np.zeros((478, 3), dtype=np.float64)
        idx = M._IDX
        # Eyes open (EAR ~0.3), mouth closed, brows at a neutral gap.
        lm[idx['eyeA_out']] = [0.30, 0.40, 0]
        lm[idx['eyeA_in']] = [0.42, 0.40, 0]
        lm[idx['eyeA_up']] = [0.36, 0.38, 0]
        lm[idx['eyeA_lo']] = [0.36, 0.42, 0]
        lm[idx['eyeB_in']] = [0.58, 0.40, 0]
        lm[idx['eyeB_out']] = [0.70, 0.40, 0]
        lm[idx['eyeB_up']] = [0.64, 0.38, 0]
        lm[idx['eyeB_lo']] = [0.64, 0.42, 0]
        lm[idx['brA_in']] = [0.38, 0.34, 0]
        lm[idx['brB_in']] = [0.62, 0.34, 0]
        lm[idx['brA_out']] = [0.30, 0.34, 0]
        lm[idx['brB_out']] = [0.70, 0.34, 0]
        lm[idx['mouth_l']] = [0.42, 0.62, 0]
        lm[idx['mouth_r']] = [0.58, 0.62, 0]
        lm[idx['lip_up_in']] = [0.50, 0.61, 0]
        lm[idx['lip_lo_in']] = [0.50, 0.63, 0]
        lm[idx['lip_up_out']] = [0.50, 0.60, 0]
        lm[idx['lip_lo_out']] = [0.50, 0.64, 0]
        lm[idx['nose_bridge']] = [0.50, 0.45, 0]
        return lm

    def test_determinism(self):
        lm = self._neutral()
        self.assertEqual(self.analyzer.extract_action_units(lm),
                         self.analyzer.extract_action_units(lm))

    def test_zeros_are_all_inactive(self):
        aus = self.analyzer.extract_action_units(np.zeros((468, 3)))
        for au in (1, 2, 4, 5, 6, 12, 25, 26, 45):
            self.assertEqual(aus[au], 0.0)

    def test_open_mouth_raises_au25_and_au26(self):
        lm = self._neutral()
        neutral = self.analyzer.extract_action_units(lm)
        lm[MicroExpressionAnalyzer._IDX['lip_lo_in']] = [0.50, 0.70, 0]
        lm[MicroExpressionAnalyzer._IDX['lip_lo_out']] = [0.50, 0.74, 0]
        opened = self.analyzer.extract_action_units(lm)
        self.assertGreater(opened[25], neutral[25])
        self.assertGreater(opened[26], neutral[26])

    def test_closed_eyes_raise_blink_au45(self):
        lm = self._neutral()
        # Collapse both eyes vertically (lids meet) -> low EAR -> blink.
        for k in ('eyeA_up', 'eyeA_lo', 'eyeB_up', 'eyeB_lo'):
            i = MicroExpressionAnalyzer._IDX[k]
            lm[i] = [lm[i][0], 0.40, 0]
        aus = self.analyzer.extract_action_units(lm)
        self.assertGreater(aus[45], 0.5)


class ExpressionGatingTests(TestCase):
    """Micro-expression scores and gates ONLY with a real landmark source."""

    def setUp(self):
        self.analyzer = MicroExpressionAnalyzer()

    def _seed(self, history):
        """Populate au_history AND the sticky derived facts exactly as observe()
        would, so scoring reads the same source-of-truth (blink flag + frame
        count) that survives a Redis hand-off -- not the truncatable list."""
        self.analyzer.au_history = deque(
            history, maxlen=MicroExpressionAnalyzer.AU_HISTORY_FRAMES)
        self.analyzer.au_timestamps = deque(
            (float(i) for i in range(len(history))),
            maxlen=MicroExpressionAnalyzer.AU_HISTORY_FRAMES)
        self.analyzer._au_frames_seen = len(history)
        # Same threshold observe() applies, read from the analyzer rather than
        # re-typed here, so a retune cannot leave these tests asserting the old
        # rule instead of failing.
        self.analyzer._blinked = any(
            a.get(45, 0.0) > MicroExpressionAnalyzer.BLINK_AU45_THRESHOLD
            for a in history)

    def test_no_score_without_real_source(self):
        # Enough frames, but no real landmarker => excluded (None), never a pass.
        self._seed([{45: 0.0, 12: 0.1} for _ in range(30)])
        with patch.object(MicroExpressionAnalyzer, 'has_real_landmark_source',
                          return_value=False):
            self.assertIsNone(self.analyzer.get_session_expression_score())

    def test_score_requires_minimum_frames(self):
        self._seed([{45: 0.0} for _ in range(3)])
        with patch.object(MicroExpressionAnalyzer, 'has_real_landmark_source',
                          return_value=True):
            self.assertIsNone(self.analyzer.get_session_expression_score())

    def test_au_history_is_bounded_so_both_backends_score_alike(self):
        """The motion score must not depend on which store the session lives in.

        au_history used to grow without limit while snapshot_state truncated to
        the recent window, so an in-memory session scored over every frame and a
        Redis-handed-off one scored over only the tail -- the same session, two
        verdicts. Bounding the append side to the snapshot window makes a
        round-tripped analyzer score identically to the one that observed.
        """
        cap = MicroExpressionAnalyzer.AU_HISTORY_FRAMES
        # Overrun the window, with an early blink that truncation would drop.
        history = [{45: 0.9, 12: 0.4}] + [
            {45: 0.0, 12: 0.1 + (i % 7) * 0.05} for i in range(cap + 200)]
        self._seed(history)
        self.assertEqual(len(self.analyzer.au_history), cap)

        far_side = MicroExpressionAnalyzer()
        far_side.restore_state(self.analyzer.snapshot_state())
        self.assertEqual(len(far_side.au_history), cap)
        with patch.object(MicroExpressionAnalyzer, 'has_real_landmark_source',
                          return_value=True):
            self.assertEqual(self.analyzer.get_session_expression_score(),
                             far_side.get_session_expression_score())
        # The early blink survives via the sticky flag, not the truncated track.
        self.assertTrue(far_side._blinked)

    def test_blink_and_motion_produce_a_score(self):
        # A live track: a blink plus AU variation over time.
        hist = []
        for i in range(30):
            hist.append({45: 1.0 if i == 15 else 0.0,
                         12: 0.4 if i % 2 else 0.0, 1: 0.1 * (i % 3)})
        self._seed(hist)
        with patch.object(MicroExpressionAnalyzer, 'has_real_landmark_source',
                          return_value=True):
            score = self.analyzer.get_session_expression_score()
        self.assertIsNotNone(score)
        self.assertGreater(score, 0.5)  # blink (0.5) + real motion

    def test_static_track_scores_low(self):
        # A photo: no blink, flat AU track -> near-zero score, cannot gate.
        self._seed([{45: 0.0, 12: 0.0, 1: 0.0} for _ in range(30)])
        with patch.object(MicroExpressionAnalyzer, 'has_real_landmark_source',
                          return_value=True):
            score = self.analyzer.get_session_expression_score()
        self.assertIsNotNone(score)
        self.assertEqual(score, 0.0)

    def test_blink_survives_history_truncation(self):
        """A blink observed before the bounded window must still score across a
        snapshot/restore (the sticky flag, not the truncated list, is read)."""
        from .services.session_store import serialize_session
        # Blink at frame 0, then enough later frames to push it out of a small
        # window; the sticky flag must persist through snapshot_state/restore.
        blink_first = [{45: 1.0, 12: 0.0}] + [{45: 0.0, 12: 0.4 if i % 2 else 0.0}
                                              for i in range(30)]
        self._seed(blink_first)
        snap = self.analyzer.snapshot_state()
        fresh = MicroExpressionAnalyzer()
        fresh.restore_state(snap)
        self.assertTrue(fresh._blinked)
        with patch.object(MicroExpressionAnalyzer, 'has_real_landmark_source',
                          return_value=True):
            score = fresh.get_session_expression_score()
        self.assertGreaterEqual(score, 0.5)  # blink component preserved

    def test_capabilities_micro_expression_tracks_real_source(self):
        from .services.liveness_session_service import LivenessSessionService
        svc = LivenessSessionService()
        with patch.object(MicroExpressionAnalyzer, 'has_real_landmark_source',
                          return_value=False):
            caps = svc.get_capabilities()
        self.assertFalse(caps['modalities']['micro_expression']['gates_verdict'])
        with patch.object(MicroExpressionAnalyzer, 'has_real_landmark_source',
                          return_value=True):
            caps = svc.get_capabilities()
        self.assertTrue(caps['modalities']['micro_expression']['gates_verdict'])
