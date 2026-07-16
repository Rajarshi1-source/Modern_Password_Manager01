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
        """An unknown/malformed session id must not raise."""
        from .views import persist_session_result
        from .services.liveness_session_service import SessionResult
        persist_session_result(SessionResult(
            session_id='not-a-uuid', is_verified=False, overall_liveness_score=0.0,
            deepfake_probability=0.0, confidence=0.0, micro_expression_score=0.0,
            gaze_tracking_score=0.0, pulse_oximetry_score=0.0, thermal_score=0.0,
            texture_artifact_score=0.0, total_frames_processed=0,
            duration_ms=0.0, verdict='INSUFFICIENT_SIGNAL', details={}))

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

    def test_completed_session_cannot_be_rescored(self):
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        self._inject_pulse(session)
        self.service.complete_session(sid)
        with self.assertRaises(ValueError):
            self.service.complete_session(sid)
        res = self.service.process_frame(sid, np.zeros((120, 120, 3), np.uint8), 0.0)
        self.assertIn('error', res)

    def test_completed_verdict_survives_expiry(self):
        """A completed session must not be reclassified as expired and re-scored."""
        from django.utils import timezone as dj_timezone
        from datetime import timedelta
        sid = self.service.create_session(user_id=1)['session_id']
        session = self.service.active_sessions[sid]
        self._inject_pulse(session)
        self.service.complete_session(sid)
        # Push the deadline into the past; the terminal verdict must hold.
        session['expires_at'] = dj_timezone.now() - timedelta(seconds=1)
        res = self.service.process_frame(sid, np.zeros((120, 120, 3), np.uint8), 0.0)
        self.assertEqual(res.get('error'), 'Session already completed')
        with self.assertRaises(ValueError):
            self.service.complete_session(sid)

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
        out = self.service.submit_challenge_response(
            sid, {'sequence': gaze_ch['sequence'], 'gaze_data': client})
        self.assertFalse(out['passed'])
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
        """A just-completed session stays long enough to keep rejecting replays."""
        sid = self.service.create_session(user_id=1)['session_id']
        self.service.complete_session(sid)
        self.service.create_session(user_id=1)
        self.assertIn(sid, self.service.active_sessions)
        with self.assertRaises(ValueError):
            self.service.complete_session(sid)

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
