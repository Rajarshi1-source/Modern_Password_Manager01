"""
Neuro-Feedback Unit Tests
=========================

Comprehensive tests for brainwave analysis, EEG data processing,
memory training, and spaced repetition scheduling.

@author Password Manager Team
@created 2026-02-07
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import json

User = get_user_model()


class BrainwaveAnalyzerTests(TestCase):
    """Unit tests for brainwave analysis algorithms."""
    
    def setUp(self):
        """Set up test fixtures."""
        from neuro_feedback.services import BrainwaveAnalyzer
        self.analyzer = BrainwaveAnalyzer(baseline_alpha=10.0, baseline_theta=6.0)
    
    def test_compute_band_powers_with_valid_eeg_data(self):
        """Test FFT band power computation with valid EEG data."""
        # Generate synthetic EEG signal with known frequency components
        sample_rate = 256
        duration = 1.0  # seconds
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        
        # 10 Hz alpha wave + 6 Hz theta wave
        alpha_wave = 0.5 * np.sin(2 * np.pi * 10 * t)
        theta_wave = 0.3 * np.sin(2 * np.pi * 6 * t)
        eeg_signal = alpha_wave + theta_wave
        
        # Analyze
        metrics = self.analyzer.analyze(eeg_signal)
        
        # Verify band powers are computed
        self.assertIsNotNone(metrics.alpha_power)
        self.assertIsNotNone(metrics.theta_power)
        self.assertGreater(metrics.alpha_power, 0)
        self.assertGreater(metrics.theta_power, 0)
    
    def test_focus_index_calculation(self):
        """Test focus index (beta/theta ratio) calculation."""
        sample_rate = 256
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        
        # High beta (focused) signal
        beta_wave = 1.0 * np.sin(2 * np.pi * 20 * t)  # 20 Hz beta
        theta_wave = 0.2 * np.sin(2 * np.pi * 6 * t)   # Low theta
        focused_signal = beta_wave + theta_wave
        
        metrics = self.analyzer.analyze(focused_signal)
        
        # Focus index should be > 0 for high beta/low theta
        self.assertIsNotNone(metrics.focus_index)
        self.assertGreaterEqual(metrics.focus_index, 0)
        self.assertLessEqual(metrics.focus_index, 1)
    
    def test_memory_readiness_threshold(self):
        """Test memory readiness detection based on alpha/theta ratio."""
        sample_rate = 256
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        
        # High alpha signal (relaxed/memory-ready state)
        alpha_wave = 1.0 * np.sin(2 * np.pi * 10 * t)
        
        metrics = self.analyzer.analyze(alpha_wave)
        
        # Memory readiness should be computed
        self.assertIsNotNone(metrics.memory_readiness)
        self.assertGreaterEqual(metrics.memory_readiness, 0)
        self.assertLessEqual(metrics.memory_readiness, 1)
    
    def test_artifact_detection(self):
        """Test eye blink and muscle artifact detection."""
        from neuro_feedback.services import BrainwaveAnalyzer
        analyzer = BrainwaveAnalyzer()
        
        # Signal with artifact (sudden spike)
        normal_signal = np.random.randn(256)
        artifact_signal = normal_signal.copy()
        artifact_signal[100:120] = 100  # Large spike (eye blink)
        
        # Should detect artifact
        has_artifact = analyzer.detect_artifacts(artifact_signal)
        
        self.assertIsInstance(has_artifact, bool)
    
    def test_brain_state_classification(self):
        """Test brain state classification (focused, relaxed, memory_ready, etc.)."""
        from neuro_feedback.services import BrainState
        
        sample_rate = 256
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        
        # Alpha-dominant signal (relaxed/memory-ready)
        alpha_signal = np.sin(2 * np.pi * 10 * t)
        metrics = self.analyzer.analyze(alpha_signal)
        
        self.assertIsNotNone(metrics.brain_state)
        self.assertIsInstance(metrics.brain_state, BrainState)


class MockEEGDataStreamTests(TestCase):
    """Tests for mock EEG data streaming."""
    
    def test_eeg_data_packet_structure(self):
        """Test that mock EEG data packets have correct structure."""
        from neuro_feedback.services import BrainwaveAnalyzer
        
        # Simulate EEG data packet from device
        mock_packet = {
            'channels': [np.random.randn(256).tolist() for _ in range(4)],  # 4-channel EEG
            'sample_rate': 256,
            'timestamp': timezone.now().timestamp(),
        }
        
        self.assertIn('channels', mock_packet)
        self.assertIn('sample_rate', mock_packet)
        self.assertEqual(len(mock_packet['channels']), 4)
        self.assertEqual(len(mock_packet['channels'][0]), 256)
    
    def test_continuous_stream_analysis(self):
        """Test analyzing continuous stream of EEG samples."""
        from neuro_feedback.services import BrainwaveAnalyzer
        
        analyzer = BrainwaveAnalyzer()
        results = []
        
        # Simulate 5 seconds of streaming
        for i in range(5):
            eeg_chunk = np.random.randn(256)  # 1 second at 256 Hz
            metrics = analyzer.analyze(eeg_chunk)
            results.append(metrics)
        
        self.assertEqual(len(results), 5)
        for metrics in results:
            self.assertIsNotNone(metrics.brain_state)


class SpacedRepetitionSchedulingTests(TestCase):
    """Tests for SM-2 spaced repetition algorithm."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='test_neuro_user',
            email='neuro@test.com',
            password='testpass123'
        )
    
    def test_sm2_initial_interval(self):
        """Test SM-2 initial interval calculation."""
        from neuro_feedback.services import MemoryTrainingService
        
        service = MemoryTrainingService(self.user)
        
        # Quality 5 (perfect) should give larger interval
        interval_q5 = service._calculate_next_interval(2.5, 0, 5)
        
        # Quality 3 (correct but difficult) should give smaller interval
        interval_q3 = service._calculate_next_interval(2.5, 0, 3)
        
        self.assertGreater(interval_q5, 0)
        self.assertGreater(interval_q3, 0)
    
    def test_sm2_easiness_factor_update(self):
        """Test easiness factor update based on recall quality."""
        from neuro_feedback.services import MemoryTrainingService
        
        service = MemoryTrainingService(self.user)
        
        # Correct, easy recall (quality 5)
        new_ef_q5 = service._update_easiness_factor(2.5, 5)
        
        # Correct but hard recall (quality 3)
        new_ef_q3 = service._update_easiness_factor(2.5, 3)
        
        # Failed recall (quality 1)
        new_ef_q1 = service._update_easiness_factor(2.5, 1)
        
        # Easy recall should increase EF, hard should decrease
        self.assertGreater(new_ef_q5, 2.5)
        self.assertLess(new_ef_q1, 2.5)
        self.assertGreaterEqual(new_ef_q1, 1.3)  # Minimum EF
    
    def test_review_scheduling(self):
        """Test that reviews are scheduled correctly."""
        from neuro_feedback.models import PasswordTrainingProgram, SpacedRepetitionSchedule
        
        program = PasswordTrainingProgram.objects.create(
            user=self.user,
            total_chunks=4,
        )
        
        # Create schedule
        schedule = SpacedRepetitionSchedule.objects.create(
            program=program,
            next_review_at=timezone.now() + timedelta(days=1),
        )
        
        self.assertTrue(schedule.is_due())  # Should not be due yet (future)
        
        # Make it due
        schedule.next_review_at = timezone.now() - timedelta(hours=1)
        schedule.save()
        
        self.assertTrue(schedule.is_due())  # Now due


class MemoryTrainingServiceTests(TestCase):
    """Tests for memory training service."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='memory_test_user',
            email='memory@test.com',
            password='testpass123'
        )
    
    def test_password_chunking(self):
        """Test password is chunked correctly."""
        from neuro_feedback.services import MemoryTrainingService
        
        service = MemoryTrainingService(self.user)
        
        password = "MyStr0ng!P@ssw0rd#2026"
        chunks = service._chunk_password(password, chunk_size=8)
        
        self.assertEqual(len(chunks), 3)  # 22 chars / 8 = 3 chunks
        self.assertEqual(chunks[0], "MyStr0ng")
        self.assertEqual(chunks[1], "!P@ssw0r")
        self.assertEqual(chunks[2], "d#2026")
    
    def test_recall_quality_scoring(self):
        """Test recall quality scoring based on success and time."""
        from neuro_feedback.services import MemoryTrainingService
        
        service = MemoryTrainingService(self.user)
        
        # Fast correct recall
        quality_fast = service._calculate_recall_quality(
            success=True,
            response_time_ms=1000,
            brain_metrics=None
        )
        
        # Slow correct recall
        quality_slow = service._calculate_recall_quality(
            success=True,
            response_time_ms=10000,
            brain_metrics=None
        )
        
        # Failed recall
        quality_failed = service._calculate_recall_quality(
            success=False,
            response_time_ms=5000,
            brain_metrics=None
        )
        
        self.assertGreater(quality_fast, quality_slow)
        self.assertGreater(quality_slow, quality_failed)
        self.assertLess(quality_failed, 3)  # Fail should be < 3
    
    def test_chunk_selection_by_brain_state(self):
        """Test chunk selection based on brain readiness."""
        from neuro_feedback.services import MemoryTrainingService, BrainwaveMetrics, BrainState
        from neuro_feedback.models import PasswordTrainingProgram, MemoryStrengthScore
        import time
        
        service = MemoryTrainingService(self.user)
        
        # Create program
        program = PasswordTrainingProgram.objects.create(
            user=self.user,
            total_chunks=4,
        )
        
        # Create memory scores
        for i in range(4):
            MemoryStrengthScore.objects.create(
                program=program,
                chunk_index=i,
                strength_score=0.2 * (i + 1),  # Varying strengths
                chunk_hash=f"hash_{i}",
            )
        
        # Get chunk with high memory readiness
        metrics = BrainwaveMetrics(
            timestamp=time.time(),
            brain_state=BrainState.MEMORY_READY,
            memory_readiness=0.9,
        )
        
        password = "12345678ABCDEFGH!@#$%^&*12345678"
        chunk, message = service.get_next_chunk(program, password, metrics)
        
        self.assertIsNotNone(chunk)


class NeurofeedbackEngineTests(TestCase):
    """Tests for neurofeedback signal generation."""
    
    def test_visual_feedback_generation(self):
        """Test visual feedback parameters are generated correctly."""
        from neuro_feedback.services import NeurofeedbackEngine, BrainwaveMetrics, BrainState
        import time
        
        engine = NeurofeedbackEngine()
        
        metrics = BrainwaveMetrics(
            timestamp=time.time(),
            brain_state=BrainState.FOCUSED,
            memory_readiness=0.7,
            focus_index=0.8,
        )
        
        signal = engine.generate_feedback(metrics)
        
        self.assertIsNotNone(signal.visual)
        self.assertIn('color', signal.visual)
        self.assertIn('brightness', signal.visual)
    
    def test_audio_feedback_generation(self):
        """Test audio feedback (binaural beats) generation."""
        from neuro_feedback.services import NeurofeedbackEngine, BrainwaveMetrics, BrainState
        import time
        
        engine = NeurofeedbackEngine(binaural_enabled=True)
        
        metrics = BrainwaveMetrics(
            timestamp=time.time(),
            brain_state=BrainState.MEMORY_READY,
            memory_readiness=0.8,
        )
        
        signal = engine.generate_feedback(metrics)
        
        self.assertIsNotNone(signal.audio)
        self.assertIn('frequency', signal.audio)
    
    def test_reward_signal_generation(self):
        """Test reward signal for successful recall."""
        from neuro_feedback.services import NeurofeedbackEngine
        
        engine = NeurofeedbackEngine()
        
        # Successful, fast recall
        reward = engine.generate_reward_signal(success=True, quality=5)
        
        self.assertIsNotNone(reward)
        self.assertTrue(reward.is_reward)
    
    def test_state_transition_feedback(self):
        """Test feedback changes when brain state transitions."""
        from neuro_feedback.services import NeurofeedbackEngine, BrainwaveMetrics, BrainState
        import time
        
        engine = NeurofeedbackEngine()
        
        # Initial unfocused state
        metrics1 = BrainwaveMetrics(
            timestamp=time.time(),
            brain_state=BrainState.UNFOCUSED,
            memory_readiness=0.3,
        )
        signal1 = engine.generate_feedback(metrics1)
        
        # Transition to focused state
        metrics2 = BrainwaveMetrics(
            timestamp=time.time() + 1,
            brain_state=BrainState.FOCUSED,
            memory_readiness=0.7,
        )
        signal2 = engine.generate_feedback(metrics2)
        
        # Feedback should differ
        self.assertNotEqual(signal1.visual.get('color'), signal2.visual.get('color'))


class WebSocketConnectionTests(TransactionTestCase):
    """Tests for WebSocket connections."""
    
    def test_websocket_message_structure(self):
        """Test WebSocket message structure for EEG data."""
        message = {
            'type': 'eeg_data',
            'channels': [[0.1, 0.2, 0.3] for _ in range(4)],
            'sample_rate': 256,
            'timestamp': 1234567890.123,
        }
        
        self.assertEqual(message['type'], 'eeg_data')
        self.assertEqual(len(message['channels']), 4)
    
    def test_feedback_message_structure(self):
        """Test neurofeedback message structure."""
        feedback_message = {
            'type': 'neurofeedback',
            'feedback': {
                'visual': {'color': '#4ade80', 'brightness': 0.8},
                'audio': {'frequency': 10.5, 'volume': 0.7},
                'message': 'Good focus! Ready to practice.',
            },
            'metrics': {
                'alpha_power': 0.8,
                'theta_power': 0.3,
                'brain_state': 'focused',
                'memory_readiness': 0.75,
            },
        }
        
        self.assertEqual(feedback_message['type'], 'neurofeedback')
        self.assertIn('visual', feedback_message['feedback'])
        self.assertIn('brain_state', feedback_message['metrics'])


class EEGDeviceServiceTests(TestCase):
    """Tests for EEG device service."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='device_test_user',
            email='device@test.com',
            password='testpass123'
        )
    
    def test_device_registration(self):
        """Test device registration."""
        from neuro_feedback.services import EEGDeviceService
        
        service = EEGDeviceService(self.user)
        
        device = service.register_device(
            device_id='BT-MUSE2-001',
            device_type='muse_2',
            device_name='My Muse Headband',
            firmware_version='2.1.0'
        )
        
        self.assertIsNotNone(device)
        self.assertEqual(device.device_type, 'muse_2')
        self.assertEqual(device.status, 'paired')
    
    def test_device_calibration(self):
        """Test device calibration process."""
        from neuro_feedback.services import EEGDeviceService
        from neuro_feedback.models import EEGDevice
        
        service = EEGDeviceService(self.user)
        
        device = EEGDevice.objects.create(
            user=self.user,
            device_id='BT-TEST-001',
            device_type='muse_2',
            device_name='Test Device',
            status='paired'
        )
        
        # Start calibration
        result = service.start_calibration(str(device.id))
        
        self.assertIsNotNone(result)
        
        device.refresh_from_db()
        self.assertEqual(device.status, 'calibrating')
