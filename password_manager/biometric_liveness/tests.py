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
        """Give the session one server-observed gaze sample inside the challenge
        window, and a deterministic challenge verdict (bypasses the estimator,
        which is capability-gated)."""
        from .services.gaze_tracking_service import GazePoint, TaskResult, CognitiveTaskType
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
        """With a real estimator, gaze reports available and gating."""
        self.service.gaze_service.has_real_gaze_model = lambda: True
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
        # Real estimator present, but the gaze challenge is never answered.
        session['services']['gaze'].has_real_gaze_model = lambda: True
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
        """With gaze measurable, letting the window lapse is a skip, not a gap."""
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        gaze_ch, _ = self._open_gaze_window(session)
        # Pretend a real estimator is loaded, but observe no gaze at all.
        session['services']['gaze'].has_real_gaze_model = lambda: True
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

    def test_late_challenge_response_rejected(self):
        """A response arriving long after the window closed cannot pass."""
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        self._stub_gaze(session, passed=True)
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
        # Gaze is NOT measurable here (no estimator), so an expired window is a
        # capability gap, not a skip: it must not veto. Vetoing on an
        # unmeasurable modality would fail every session in the gated state.
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
