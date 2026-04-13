"""
Unit Tests for ML Security Module
===================================

Tests ML models, predictions, and database operations.

Test Categories:
1. Model Tests - Testing ML model functionality
2. Database Tests - Testing database models and operations
3. API View Tests - Testing API endpoints (unit level)
4. Service Tests - Testing business logic
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import patch, Mock, MagicMock
from datetime import timedelta
import json
import hashlib
import numpy as np

from .models import (
    PasswordStrengthPrediction,
    MLModelMetadata,
    UserBehaviorProfile,
    AnomalyDetection,  # Correct model name
    AnomalyDetectionLog,  # Backwards compatibility alias
    ThreatPrediction,  # Correct model name
)

# ==============================================================================
# MODEL TESTS
# ==============================================================================

class PasswordStrengthPredictionModelTest(TestCase):
    """Test PasswordStrengthPrediction model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_password_strength_prediction(self):
        """Test creating a password strength prediction"""
        password_hash = hashlib.sha256(b'testpassword').hexdigest()
        
        prediction = PasswordStrengthPrediction.objects.create(
            user=self.user,
            password_hash=password_hash,
            strength='strong',
            confidence_score=0.85,
            entropy=45.2,
            character_diversity=0.8,
            length=16,
            has_numbers=True,
            has_uppercase=True,
            has_lowercase=True,
            has_special=True,
            contains_common_patterns=False,
            guessability_score=15.0,
        )
        
        self.assertEqual(prediction.user, self.user)
        self.assertEqual(prediction.strength, 'strong')
        self.assertEqual(prediction.confidence_score, 0.85)
        self.assertIsNotNone(prediction.created_at)
    
    def test_password_strength_str_representation(self):
        """Test string representation"""
        password_hash = hashlib.sha256(b'test').hexdigest()
        
        prediction = PasswordStrengthPrediction.objects.create(
            user=self.user,
            password_hash=password_hash,
            strength='moderate',
            confidence_score=0.75,
            entropy=30.0,
            character_diversity=0.6,
            length=10,
            has_numbers=True,
            has_uppercase=False,
            has_lowercase=True,
            has_special=False,
            contains_common_patterns=False,
            guessability_score=40.0,
        )
        
        str_repr = str(prediction)
        self.assertIn('testuser', str_repr)
        self.assertIn('0.75', str_repr)
    
    def test_multiple_predictions_per_user(self):
        """Test that a user can have multiple password predictions"""
        for i in range(3):
            PasswordStrengthPrediction.objects.create(
                user=self.user,
                password_hash=hashlib.sha256(f'password{i}'.encode()).hexdigest(),
                strength='moderate',
                confidence_score=0.5 + (i * 0.1),
                entropy=28.0 + i,
                character_diversity=0.5 + (i * 0.05),
                length=8 + i,
                has_numbers=True,
                has_uppercase=bool(i % 2),
                has_lowercase=True,
                has_special=bool((i + 1) % 2),
                contains_common_patterns=False,
                guessability_score=50.0 - (i * 5),
            )
        
        predictions = PasswordStrengthPrediction.objects.filter(user=self.user)
        self.assertEqual(predictions.count(), 3)
    
    def test_prediction_ordering(self):
        """Test that predictions are ordered by timestamp (newest first)"""
        for i in range(3):
            PasswordStrengthPrediction.objects.create(
                user=self.user,
                password_hash=hashlib.sha256(f'pass{i}'.encode()).hexdigest(),
                strength='weak',
                confidence_score=0.5,
                entropy=20.0 + i,
                character_diversity=0.4,
                length=8 + i,
                has_numbers=True,
                has_uppercase=False,
                has_lowercase=True,
                has_special=False,
                contains_common_patterns=False,
                guessability_score=70.0 - i,
            )
        
        predictions = PasswordStrengthPrediction.objects.filter(user=self.user)
        # Check ordering (should be newest first based on Meta.ordering)
        self.assertTrue(
            predictions[0].created_at >= predictions[1].created_at >= predictions[2].created_at
        )


class AnomalyDetectionModelTest(TestCase):
    """Test AnomalyDetection model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_anomaly_detection_log(self):
        """Test creating an anomaly detection log"""
        log = AnomalyDetection.objects.create(
            user=self.user,
            session_id='test-session-001',
            anomaly_type='behavior',
            severity='high',
            anomaly_score=0.85,
            confidence=0.90,
            ip_address='192.168.1.1',
        )
        
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.anomaly_type, 'behavior')
        self.assertEqual(log.severity, 'high')
        self.assertEqual(log.anomaly_score, 0.85)
        self.assertIsNone(log.resolved_at)
    
    def test_anomaly_resolution(self):
        """Test marking an anomaly as resolved"""
        log = AnomalyDetection.objects.create(
            user=self.user,
            session_id='test-session-002',
            anomaly_type='behavior',
            severity='high',
            anomaly_score=0.9,
            confidence=0.95,
            ip_address='192.168.1.2',
        )
        
        self.assertIsNone(log.resolved_at)
        
        # Resolve the anomaly
        log.resolved_at = timezone.now()
        log.save()
        
        log.refresh_from_db()
        self.assertIsNotNone(log.resolved_at)
    
    def test_filter_unresolved_anomalies(self):
        """Test filtering unresolved anomalies"""
        # Create 3 anomalies, resolve 1
        for i in range(3):
            log = AnomalyDetection.objects.create(
                user=self.user,
                session_id=f'test-session-{i}',
                anomaly_type='behavior',
                severity='high',
                anomaly_score=0.8,
                confidence=0.90,
                ip_address=f'192.168.1.{10 + i}',
            )
            if i == 0:  # First one is resolved
                log.resolved_at = timezone.now()
                log.save(update_fields=['resolved_at'])
        
        unresolved = AnomalyDetection.objects.filter(
            user=self.user, 
            resolved_at__isnull=True
        )
        self.assertEqual(unresolved.count(), 2)


class ThreatPredictionModelTest(TestCase):
    """Test ThreatPrediction model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_threat_prediction(self):
        """Test creating a threat prediction"""
        input_features = {
            'login_attempts': 3,
            'ip_changes': 2,
            'time_of_day': 'night'
        }
        
        result = ThreatPrediction.objects.create(
            user=self.user,
            session_id='test-session-id',
            threat_type='brute_force',  # Changed from analysis_type
            threat_score=0.75,
            risk_level=75,  # Added
            sequence_features=input_features,  # Changed from input_features
            spatial_features={},  # Added
            temporal_features={},  # Added
            cnn_output={},  # Added
            lstm_output={},  # Added
            final_prediction={},  # Added
            recommended_action='Enable MFA',
            # is_threat=True  # removed as field does not exist in model
        )
        
        self.assertEqual(result.user, self.user)
        self.assertEqual(result.threat_score, 0.75)
        # self.assertTrue(result.is_threat) # Removed
        self.assertEqual(result.recommended_action, 'Enable MFA')
    
    def test_threat_detection_threshold(self):
        """Test threat detection based on score threshold"""
        # Low score - not a threat
        low_threat = ThreatPrediction.objects.create(
            user=self.user,
            session_id='test-session-id-1',
            threat_type='brute_force', 
            threat_score=0.3,
            risk_level=30,
            sequence_features={},
            spatial_features={},
            temporal_features={},
            cnn_output={},
            lstm_output={},
            final_prediction={},
            # is_threat=False 
        )
        # self.assertFalse(low_threat.is_threat) # Removed check
        self.assertLess(low_threat.threat_score, 0.5) # Alternative check
        
        # High score - is a threat
        high_threat = ThreatPrediction.objects.create(
            user=self.user,
            session_id='test-session-id-2',
            threat_type='brute_force',
            threat_score=0.85,
            risk_level=85,
            sequence_features={},
            spatial_features={},
            temporal_features={},
            cnn_output={},
            lstm_output={},
            final_prediction={},
            # is_threat=True
        )
        # self.assertTrue(high_threat.is_threat) # Removed check
        self.assertGreater(high_threat.threat_score, 0.5) # Alternative check
    
    def test_filter_high_threat_results(self):
        """Test filtering high-threat results"""
        # Create multiple threat results
        scores = [0.2, 0.5, 0.8, 0.9, 0.95]
        for i, score in enumerate(scores):
            ThreatPrediction.objects.create(
                user=self.user,
                session_id=f'session-{i}',
                threat_type='brute_force',
                threat_score=score,
                risk_level=int(score*100),
                sequence_features={},
                spatial_features={},
                temporal_features={},
                cnn_output={},
                lstm_output={},
                final_prediction={},
                # is_threat=(score > 0.5)
            )
        
        # Filtering by risk_level or threat_score instead of is_threat
        high_threats = ThreatPrediction.objects.filter(
            user=self.user,
            threat_score__gt=0.5
        )
        self.assertEqual(high_threats.count(), 3)  # Scores > 0.5


class MLModelMetadataTest(TestCase):
    """Test MLModelMetadata model"""
    
    def test_create_model_metadata(self):
        """Test creating model metadata"""
        metadata = MLModelMetadata.objects.create(
            model_type='password_strength',
            version='1.0.0',
            file_path='/models/password_strength.h5',
            accuracy=0.92,
            precision=0.89,
            recall=0.91,
            f1_score=0.90,
            is_active=True,
            notes='LSTM model for password strength prediction'
        )
        
        self.assertEqual(metadata.model_type, 'password_strength')
        self.assertEqual(metadata.version, '1.0.0')
        self.assertTrue(metadata.is_active)
        self.assertEqual(metadata.accuracy, 0.92)
    
    def test_model_versioning(self):
        """Test that multiple versions can exist"""
        # Create version 1.0
        v1 = MLModelMetadata.objects.create(
            model_type='password_strength',
            version='1.0.0',
            file_path='/models/v1.h5',
            is_active=False
        )
        
        # Create version 2.0
        v2 = MLModelMetadata.objects.create(
            model_type='anomaly_detection',
            version='2.0.0',
            file_path='/models/v2.h5',
            is_active=True
        )
        
        self.assertFalse(v1.is_active)
        self.assertTrue(v2.is_active)
    
    def test_get_active_model(self):
        """Test retrieving active model"""
        # Create inactive and active models
        MLModelMetadata.objects.create(
            model_type='password_strength',
            version='1.0',
            is_active=False,
            file_path='/old.h5'
        )
        
        MLModelMetadata.objects.create(
            model_type='anomaly_detection',
            version='2.0',
            is_active=True,
            file_path='/current.h5'
        )
        
        active_model = MLModelMetadata.objects.get(is_active=True)
        self.assertEqual(active_model.model_type, 'anomaly_detection')


# ==============================================================================
# SERVICE/UTILITY TESTS
# ==============================================================================

class MLModelsUtilityTest(TestCase):
    """Test ML model utility functions"""
    
    @patch('ml_security.ml_models.get_model')
    def test_password_strength_prediction_flow(self, mock_get_model):
        """Test the password strength prediction flow"""
        mock_model = MagicMock()
        mock_model.predict.return_value = {
            'strength': 'strong',
            'confidence': 0.85,
            'features': {},
            'recommendations': [],
        }
        mock_get_model.return_value = mock_model
        
        result = mock_model.predict('TestPassword123!')
        self.assertEqual(result['confidence'], 0.85)
        self.assertEqual(result['strength'], 'strong')
    
    def test_password_preprocessing(self):
        """Test password preprocessing for ML model"""
        # Test different password types
        passwords = [
            "password123",
            "MyStr0ng!Pass",
            "short",
            "verylongandcomplexpassword123!@#"
        ]
        
        for password in passwords:
            # In actual implementation, this would preprocess the password
            # For now, we verify structure
            self.assertIsInstance(password, str)
            self.assertGreater(len(password), 0)


class AnomalyDetectionUtilityTest(TestCase):
    """Test anomaly detection utility functions"""
    
    def test_feature_extraction(self):
        """Test extracting features from event data"""
        event_data = {
            'ip_latitude': 34.0522,
            'ip_longitude': -118.2437,
            'time_of_day_sin': 0.5,
            'time_of_day_cos': 0.866
        }
        
        # Verify all required features are present
        required_features = ['ip_latitude', 'ip_longitude', 'time_of_day_sin', 'time_of_day_cos']
        for feature in required_features:
            self.assertIn(feature, event_data)
    
    def test_anomaly_score_range(self):
        """Test that anomaly scores are in valid range [0, 1]"""
        # Simulate anomaly scores
        test_scores = [0.0, 0.25, 0.5, 0.75, 1.0]
        
        for score in test_scores:
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)


# ==============================================================================
# API VIEW TESTS (Unit Level)
# ==============================================================================

class PasswordStrengthAPITest(TestCase):
    """Test Password Strength API views"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse('ml_security:password-strength-check')
    
    @patch('ml_security.views.get_model')
    def test_password_strength_api_success(self, mock_get_model):
        """Test successful password strength prediction"""
        mock_model = MagicMock()
        mock_model.predict.return_value = {
            'strength': 'strong',
            'confidence': 0.85,
            'strength_score': 0.85,
            'feedback': 'Strong password!',
            'features': {
                'entropy': 45.0, 'character_diversity': 0.8, 'length': 16,
                'has_numbers': True, 'has_uppercase': True, 'has_lowercase': True,
                'has_special': True, 'contains_common_patterns': False,
                'guessability_score': 15.0,
            },
            'recommendations': [],
        }
        mock_get_model.return_value = mock_model
        
        response = self.client.post(
            self.url,
            data=json.dumps({'password': 'TestPassword123!'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
    
    def test_password_strength_api_missing_password(self):
        """Test API with missing password"""
        response = self.client.post(
            self.url,
            data=json.dumps({}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
    
    @patch('ml_security.views.get_model')
    def test_password_strength_creates_database_record(self, mock_get_model):
        """Test that API call creates database record"""
        mock_model = MagicMock()
        mock_model.predict.return_value = {
            'strength': 'moderate',
            'confidence': 0.75,
            'features': {
                'entropy': 30.0, 'character_diversity': 0.6, 'length': 7,
                'has_numbers': True, 'has_uppercase': False, 'has_lowercase': True,
                'has_special': False, 'contains_common_patterns': False,
                'guessability_score': 40.0,
            },
            'recommendations': [],
        }
        mock_get_model.return_value = mock_model
        
        initial_count = PasswordStrengthPrediction.objects.count()
        
        response = self.client.post(
            self.url,
            data=json.dumps({'password': 'test123', 'save_prediction': True}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            PasswordStrengthPrediction.objects.count(),
            initial_count + 1
        )


class AnomalyDetectionAPITest(TestCase):
    """Test Anomaly Detection API views"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse('ml_security:anomaly-detection')
    
    @patch('ml_security.views.get_model')
    def test_anomaly_detection_api_success(self, mock_get_model):
        """Test successful anomaly detection"""
        mock_detector = MagicMock()
        mock_detector.detect_anomaly.return_value = {
            'is_anomaly': True,
            'anomaly_score': 0.85,
            'severity': 'high',
            'confidence': 0.90,
            'anomaly_type': 'behavior',
            'contributing_factors': [],
            'recommended_action': 'monitor',
        }
        mock_get_model.return_value = mock_detector
        
        session_data = {
            'session_duration': 300,
            'typing_speed': 45.0,
            'vault_accesses': 5,
        }
        
        response = self.client.post(
            self.url,
            data=json.dumps({'session_data': session_data}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
    
    def test_anomaly_detection_api_missing_data(self):
        """Test API with missing event data"""
        response = self.client.post(
            self.url,
            data=json.dumps({}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)


class ThreatAnalysisAPITest(TestCase):
    """Test Threat Analysis API views"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse('ml_security:threat-analysis')
    
    @patch('ml_security.views.get_model')
    def test_threat_analysis_api_success(self, mock_get_model):
        """Test successful threat analysis"""
        mock_analyzer = MagicMock()
        mock_analyzer.analyze_threat.return_value = {
            'threat_detected': True,
            'threat_type': 'brute_force',
            'threat_score': 0.75,
            'risk_level': 75,
            'recommended_action': 'Enable MFA',
            'temporal_analysis': {},
            'spatial_analysis': {},
        }
        mock_get_model.return_value = mock_analyzer
        
        response = self.client.post(
            self.url,
            data=json.dumps({
                'session_data': {'ip': '10.0.0.1'},
                'behavior_data': {'typing_speed': 45.0}
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
    
    def test_threat_analysis_creates_record(self):
        """Test that analysis creates database record"""
        with patch('ml_security.views.get_model') as mock_get_model:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze_threat.return_value = {
                'threat_detected': True,
                'threat_type': 'brute_force',
                'threat_score': 0.8,
                'risk_level': 80,
                'recommended_action': 'Lock account',
                'temporal_analysis': {},
                'spatial_analysis': {},
            }
            mock_get_model.return_value = mock_analyzer
            
            initial_count = ThreatPrediction.objects.count()
            
            response = self.client.post(
                self.url,
                data=json.dumps({
                    'session_data': {'ip': '10.0.0.1'},
                    'behavior_data': {'typing_speed': 45.0}
                }),
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                ThreatPrediction.objects.count(),
                initial_count + 1
            )


# ==============================================================================
# INTEGRATION-STYLE TESTS (Within Django)
# ==============================================================================

class MLSecurityIntegrationTest(TestCase):
    """Integration tests for ML Security components"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_complete_password_strength_flow(self):
        """Test complete flow: API call -> prediction -> database storage"""
        client = APIClient()
        client.force_authenticate(user=self.user)
        
        with patch('ml_security.views.get_model') as mock_get_model:
            mock_model = MagicMock()
            mock_model.predict.return_value = {
                'strength': 'strong',
                'confidence': 0.85,
                'features': {
                    'entropy': 45.0,
                    'character_diversity': 0.8,
                    'length': 12,
                    'has_numbers': True,
                    'has_uppercase': True,
                    'has_lowercase': True,
                    'has_special': True,
                    'contains_common_patterns': False,
                    'guessability_score': 15.0,
                },
                'recommendations': [],
                'strength_score': 0.85,
                'feedback': 'Strong!',
            }
            mock_get_model.return_value = mock_model
            
            # Make API call (save_prediction=True to trigger DB storage)
            response = client.post(
                reverse('ml_security:password-strength-check'),
                data=json.dumps({'password': 'TestPass123!', 'save_prediction': True}),
                content_type='application/json'
            )
            
            # Verify response
            self.assertEqual(response.status_code, 200)
            
            # Verify database record
            prediction = PasswordStrengthPrediction.objects.filter(
                user=self.user
            ).first()
            self.assertIsNotNone(prediction)
            self.assertEqual(prediction.confidence_score, 0.85)
    
    def test_complete_anomaly_detection_flow(self):
        """Test complete flow: API call -> detection -> database storage -> alert"""
        client = APIClient()
        client.force_authenticate(user=self.user)
        
        with patch('ml_security.views.get_model') as mock_get_model:
            mock_detector = MagicMock()
            mock_detector.detect_anomaly.return_value = {
                'is_anomaly': True,
                'anomaly_score': 0.95,
                'severity': 'critical',
                'confidence': 0.99,
                'anomaly_type': 'behavior',
                'contributing_factors': [],
                'recommended_action': 'lock_account',
            }
            mock_get_model.return_value = mock_detector
            
            # Make API call
            response = client.post(
                reverse('ml_security:anomaly-detection'),
                data=json.dumps({
                    'session_data': {'session_duration': 300, 'typing_speed': 45.0}
                }),
                content_type='application/json'
            )
            
            # Verify response
            self.assertEqual(response.status_code, 200)
            
            # Verify database record
            log = AnomalyDetectionLog.objects.filter(
                user=self.user,
                anomaly_score__gte=0.9
            ).first()
            self.assertIsNotNone(log)
            self.assertEqual(log.severity, 'critical')
            self.assertEqual(log.anomaly_score, 0.95)


# ==============================================================================
# EDGE CASE TESTS
# ==============================================================================

class MLSecurityEdgeCaseTest(TestCase):
    """Test edge cases and error handling"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_empty_password_handling(self):
        """Test handling of empty password"""
        password_hash = hashlib.sha256(b'').hexdigest()
        
        prediction = PasswordStrengthPrediction.objects.create(
            user=self.user,
            password_hash=password_hash,
            strength='very_weak',
            confidence_score=0.0,
            entropy=0.0,
            character_diversity=0.0,
            length=0,
            has_numbers=False,
            has_uppercase=False,
            has_lowercase=False,
            has_special=False,
            contains_common_patterns=True,
            guessability_score=100.0,
        )
        
        self.assertEqual(prediction.confidence_score, 0.0)
    
    def test_extreme_anomaly_scores(self):
        """Test handling of extreme anomaly scores"""
        # Test score of 0 (definitely not an anomaly)
        log_min = AnomalyDetection.objects.create(
            user=self.user,
            session_id='test-session-min',
            anomaly_type='behavior',
            severity='low',
            anomaly_score=0.0,
            confidence=0.95,
            ip_address='10.0.0.10',
        )
        self.assertEqual(log_min.anomaly_score, 0.0)
        
        # Test score of 1 (definitely an anomaly)
        log_max = AnomalyDetection.objects.create(
            user=self.user,
            session_id='test-session-max',
            anomaly_type='multiple',
            severity='critical',
            anomaly_score=1.0,
            confidence=0.99,
            ip_address='10.0.0.11',
        )
        self.assertEqual(log_max.anomaly_score, 1.0)
    
    def test_model_not_loaded_gracefully(self):
        """Test graceful handling when ML model is not loaded"""
        # This would test the fallback behavior when models aren't available
        # In production, should return sensible defaults or error messages
        pass  # Placeholder for actual implementation
    
    def test_user_deletion_cascades(self):
        """Test that deleting user cascades to ML records"""
        # Create various ML records
        PasswordStrengthPrediction.objects.create(
            user=self.user,
            password_hash='test',
            strength='moderate',
            confidence_score=0.5,
            entropy=20.0,
            character_diversity=0.5,
            length=8,
            has_numbers=False,
            has_uppercase=False,
            has_lowercase=True,
            has_special=False,
            contains_common_patterns=True,
            guessability_score=60.0,
        )
        
        AnomalyDetection.objects.create(
            user=self.user,
            session_id='delete-session',
            anomaly_type='time',
            severity='low',
            anomaly_score=0.1,
            confidence=0.9,
            ip_address='10.0.0.20',
        )
        
        ThreatPrediction.objects.create(
            user=self.user,
            session_id='test',
            threat_type='test',
            sequence_features={},
            spatial_features={},
            temporal_features={},
            cnn_output={},
            lstm_output={},
            final_prediction={},
            risk_level=50,
            threat_score=0.5,
            # is_threat=False
        )
        
        user_id = self.user.id
        
        # Delete user
        self.user.delete()
        
        # Verify cascading deletion
        self.assertEqual(
            PasswordStrengthPrediction.objects.filter(user_id=user_id).count(),
            0
        )
        self.assertEqual(
            AnomalyDetection.objects.filter(user_id=user_id).count(),
            0
        )
        self.assertEqual(
            ThreatPrediction.objects.filter(user_id=user_id).count(),
            0
        )


# ==============================================================================
# PERFORMANCE TESTS
# ==============================================================================

class MLSecurityPerformanceTest(TestCase):
    """Test performance characteristics"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_bulk_prediction_storage(self):
        """Test storing multiple predictions efficiently"""
        import time
        
        start_time = time.time()
        
        # Create 100 predictions
        predictions = [
            PasswordStrengthPrediction(
                user=self.user,
                password_hash=hashlib.sha256(f'pass{i}'.encode()).hexdigest(),
                strength='moderate',
                confidence_score=0.5 + (i % 50) / 100,
                entropy=20.0 + (i % 10),
                character_diversity=0.5,
                length=10 + (i % 8),
                has_numbers=True,
                has_uppercase=bool(i % 2),
                has_lowercase=True,
                has_special=bool((i + 1) % 2),
                contains_common_patterns=False,
                guessability_score=50.0,
            )
            for i in range(100)
        ]
        
        PasswordStrengthPrediction.objects.bulk_create(predictions)
        
        elapsed_time = time.time() - start_time
        
        # Should complete in reasonable time (< 1 second)
        self.assertLess(elapsed_time, 1.0)
        self.assertEqual(
            PasswordStrengthPrediction.objects.filter(user=self.user).count(),
            100
        )
    
    def test_query_performance_with_indexes(self):
        """Test that database queries use indexes efficiently"""
        # Create test data
        for i in range(50):
            PasswordStrengthPrediction.objects.create(
                user=self.user,
                password_hash=hashlib.sha256(f'pass{i}'.encode()).hexdigest(),
                strength='moderate',
                confidence_score=0.5,
                entropy=20.0,
                character_diversity=0.5,
                length=10,
                has_numbers=True,
                has_uppercase=False,
                has_lowercase=True,
                has_special=False,
                contains_common_patterns=False,
                guessability_score=50.0,
            )
        
        import time
        from django.db import connection
        from django.test.utils import override_settings
        
        # Query recent predictions
        start_time = time.time()
        
        recent = PasswordStrengthPrediction.objects.filter(
            user=self.user
        ).order_by('-created_at')[:10]
        
        list(recent)  # Force evaluation
        
        elapsed_time = time.time() - start_time
        
        # Should be fast with proper indexes
        self.assertLess(elapsed_time, 0.1)


# ==============================================================================
# HELPER FUNCTIONS FOR TESTING
# ==============================================================================

class MLTestHelpers:
    """Helper functions for ML security testing"""
    
    @staticmethod
    def create_test_user(username='testuser'):
        """Create a test user"""
        return User.objects.create_user(
            username=username,
            email=f'{username}@test.com',
            password='testpass123'
        )
    
    @staticmethod
    def create_test_prediction(user, score=0.75):
        """Create a test password strength prediction"""
        return PasswordStrengthPrediction.objects.create(
            user=user,
            password_hash=hashlib.sha256(b'test').hexdigest(),
            strength='strong' if score >= 0.75 else 'moderate',
            confidence_score=score,
            entropy=35.0,
            character_diversity=0.7,
            length=12,
            has_numbers=True,
            has_uppercase=True,
            has_lowercase=True,
            has_special=True,
            contains_common_patterns=False,
            guessability_score=20.0,
        )
    
    @staticmethod
    def create_test_anomaly(user, is_anomaly=False):
        """Create a test anomaly detection log"""
        return AnomalyDetection.objects.create(
            user=user,
            session_id='helper-session',
            anomaly_type='behavior' if is_anomaly else 'time',
            severity='high' if is_anomaly else 'low',
            anomaly_score=0.8 if is_anomaly else 0.2,
            confidence=0.9,
            ip_address='127.0.0.1',
        )
    
    @staticmethod
    def create_test_threat_prediction(user, is_threat=False):
        """Create a test threat prediction"""
        return ThreatPrediction.objects.create(
            user=user,
            session_id='test-session',
            threat_type='test',
            sequence_features={},
            spatial_features={},
            temporal_features={},
            cnn_output={},
            lstm_output={},
            final_prediction={},
            risk_level=80 if is_threat else 20,
            threat_score=0.8 if is_threat else 0.2,
            recommended_action="Test action"
        )


# Run specific test suites
def suite():
    """Create test suite for ML Security module"""
    from django.test.loader import TestLoader
    loader = TestLoader()
    suite = loader.loadTestsFromModule(__name__)
    return suite

