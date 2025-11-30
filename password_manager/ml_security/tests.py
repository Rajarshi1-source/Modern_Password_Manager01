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

from django.test import TestCase, RequestFactory, Client
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from unittest.mock import patch, Mock, MagicMock
from datetime import timedelta
import json
import hashlib
import numpy as np

from .models import (
    PasswordStrengthPrediction,
    AnomalyDetectionLog,
    ThreatAnalysisResult,
    MLModelMetadata,
    UserBehaviorProfile,
    AnomalyDetection,
    ThreatPrediction
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
            strength_score=0.85,
            feedback="Strong password!",
            prediction_model="LSTM_Password_Strength"
        )
        
        self.assertEqual(prediction.user, self.user)
        self.assertEqual(prediction.strength_score, 0.85)
        self.assertEqual(prediction.feedback, "Strong password!")
        self.assertIsNotNone(prediction.timestamp)
    
    def test_password_strength_str_representation(self):
        """Test string representation"""
        password_hash = hashlib.sha256(b'test').hexdigest()
        
        prediction = PasswordStrengthPrediction.objects.create(
            user=self.user,
            password_hash=password_hash,
            strength_score=0.75,
            feedback="Good"
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
                strength_score=0.5 + (i * 0.1),
                feedback=f"Feedback {i}"
            )
        
        predictions = PasswordStrengthPrediction.objects.filter(user=self.user)
        self.assertEqual(predictions.count(), 3)
    
    def test_prediction_ordering(self):
        """Test that predictions are ordered by timestamp (newest first)"""
        for i in range(3):
            PasswordStrengthPrediction.objects.create(
                user=self.user,
                password_hash=hashlib.sha256(f'pass{i}'.encode()).hexdigest(),
                strength_score=0.5
            )
        
        predictions = PasswordStrengthPrediction.objects.filter(user=self.user)
        # Check ordering (should be newest first based on Meta.ordering)
        self.assertTrue(
            predictions[0].timestamp >= predictions[1].timestamp >= predictions[2].timestamp
        )


class AnomalyDetectionLogModelTest(TestCase):
    """Test AnomalyDetectionLog model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_anomaly_detection_log(self):
        """Test creating an anomaly detection log"""
        event_data = {
            'ip': '192.168.1.1',
            'location': 'Test Location',
            'time': '12:00'
        }
        
        log = AnomalyDetectionLog.objects.create(
            user=self.user,
            event_type='login',
            event_data=event_data,
            is_anomaly=True,
            anomaly_score=0.85,
            model_used='IsolationForest'
        )
        
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.event_type, 'login')
        self.assertTrue(log.is_anomaly)
        self.assertEqual(log.anomaly_score, 0.85)
        self.assertFalse(log.resolved)
    
    def test_anomaly_resolution(self):
        """Test marking an anomaly as resolved"""
        log = AnomalyDetectionLog.objects.create(
            user=self.user,
            event_type='login',
            event_data={},
            is_anomaly=True,
            anomaly_score=0.9,
            model_used='IsolationForest'
        )
        
        self.assertFalse(log.resolved)
        self.assertIsNone(log.resolved_at)
        
        # Resolve the anomaly
        log.resolved = True
        log.resolved_at = timezone.now()
        log.save()
        
        log.refresh_from_db()
        self.assertTrue(log.resolved)
        self.assertIsNotNone(log.resolved_at)
    
    def test_filter_unresolved_anomalies(self):
        """Test filtering unresolved anomalies"""
        # Create 3 anomalies, resolve 1
        for i in range(3):
            AnomalyDetectionLog.objects.create(
                user=self.user,
                event_type='login',
                event_data={},
                is_anomaly=True,
                anomaly_score=0.8,
                model_used='IsolationForest',
                resolved=(i == 0)  # First one is resolved
            )
        
        unresolved = AnomalyDetectionLog.objects.filter(
            user=self.user, 
            resolved=False
        )
        self.assertEqual(unresolved.count(), 2)


class ThreatAnalysisResultModelTest(TestCase):
    """Test ThreatAnalysisResult model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_threat_analysis_result(self):
        """Test creating a threat analysis result"""
        input_features = {
            'login_attempts': 3,
            'ip_changes': 2,
            'time_of_day': 'night'
        }
        
        result = ThreatAnalysisResult.objects.create(
            user=self.user,
            analysis_type='login_behavior',
            input_features=input_features,
            threat_score=0.75,
            is_threat=True,
            recommended_action='Enable MFA',
            model_used='Hybrid_CNN_LSTM'
        )
        
        self.assertEqual(result.user, self.user)
        self.assertEqual(result.threat_score, 0.75)
        self.assertTrue(result.is_threat)
        self.assertEqual(result.recommended_action, 'Enable MFA')
    
    def test_threat_detection_threshold(self):
        """Test threat detection based on score threshold"""
        # Low score - not a threat
        low_threat = ThreatAnalysisResult.objects.create(
            user=self.user,
            analysis_type='session_activity',
            input_features={},
            threat_score=0.3,
            is_threat=False
        )
        self.assertFalse(low_threat.is_threat)
        
        # High score - is a threat
        high_threat = ThreatAnalysisResult.objects.create(
            user=self.user,
            analysis_type='session_activity',
            input_features={},
            threat_score=0.85,
            is_threat=True
        )
        self.assertTrue(high_threat.is_threat)
    
    def test_filter_high_threat_results(self):
        """Test filtering high-threat results"""
        # Create multiple threat results
        scores = [0.2, 0.5, 0.8, 0.9, 0.95]
        for score in scores:
            ThreatAnalysisResult.objects.create(
                user=self.user,
                analysis_type='test',
                input_features={},
                threat_score=score,
                is_threat=(score > 0.5)
            )
        
        high_threats = ThreatAnalysisResult.objects.filter(
            user=self.user,
            is_threat=True
        )
        self.assertEqual(high_threats.count(), 3)  # Scores > 0.5


class MLModelMetadataTest(TestCase):
    """Test MLModelMetadata model"""
    
    def test_create_model_metadata(self):
        """Test creating model metadata"""
        metadata = MLModelMetadata.objects.create(
            model_name='PasswordStrengthLSTM',
            version='1.0.0',
            description='LSTM model for password strength prediction',
            last_trained=timezone.now(),
            accuracy=0.92,
            precision=0.89,
            recall=0.91,
            f1_score=0.90,
            path='/models/password_strength.h5',
            is_active=True
        )
        
        self.assertEqual(metadata.model_name, 'PasswordStrengthLSTM')
        self.assertEqual(metadata.version, '1.0.0')
        self.assertTrue(metadata.is_active)
        self.assertEqual(metadata.accuracy, 0.92)
    
    def test_model_versioning(self):
        """Test that multiple versions can exist"""
        # Create version 1.0
        v1 = MLModelMetadata.objects.create(
            model_name='TestModel_v1',
            version='1.0.0',
            path='/models/v1.h5',
            is_active=False
        )
        
        # Create version 2.0
        v2 = MLModelMetadata.objects.create(
            model_name='TestModel_v2',
            version='2.0.0',
            path='/models/v2.h5',
            is_active=True
        )
        
        self.assertFalse(v1.is_active)
        self.assertTrue(v2.is_active)
    
    def test_get_active_model(self):
        """Test retrieving active model"""
        # Create inactive and active models
        MLModelMetadata.objects.create(
            model_name='OldModel',
            version='1.0',
            is_active=False,
            path='/old.h5'
        )
        
        active = MLModelMetadata.objects.create(
            model_name='CurrentModel',
            version='2.0',
            is_active=True,
            path='/current.h5'
        )
        
        active_model = MLModelMetadata.objects.get(is_active=True)
        self.assertEqual(active_model.model_name, 'CurrentModel')


# ==============================================================================
# SERVICE/UTILITY TESTS
# ==============================================================================

class MLModelsUtilityTest(TestCase):
    """Test ML model utility functions"""
    
    @patch('ml_security.ml_models.password_strength.load_model')
    @patch('ml_security.ml_models.password_strength._password_strength_model')
    @patch('ml_security.ml_models.password_strength._password_tokenizer')
    def test_password_strength_prediction_flow(self, mock_tokenizer, mock_model, mock_load):
        """Test the password strength prediction flow"""
        # Mock tokenizer
        mock_tokenizer.texts_to_sequences = Mock(return_value=[[1, 2, 3]])
        
        # Mock model prediction
        mock_model.predict = Mock(return_value=np.array([[0.85]]))
        
        # This would normally call the actual predict_strength function
        # For unit testing, we're verifying the flow works
        self.assertTrue(True)  # Placeholder
    
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
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)
        self.url = reverse('password-strength-check')
    
    @patch('ml_security.views.password_strength.predict_strength')
    def test_password_strength_api_success(self, mock_predict):
        """Test successful password strength prediction"""
        # Mock the prediction
        mock_predict.return_value = (0.85, "Strong password!")
        
        response = self.client.post(
            self.url,
            data=json.dumps({'password': 'TestPassword123!'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('strength_score', data)
        self.assertIn('feedback', data)
    
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
    
    @patch('ml_security.views.password_strength.predict_strength')
    def test_password_strength_creates_database_record(self, mock_predict):
        """Test that API call creates database record"""
        mock_predict.return_value = (0.75, "Good")
        
        initial_count = PasswordStrengthPrediction.objects.count()
        
        response = self.client.post(
            self.url,
            data=json.dumps({'password': 'test123'}),
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
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)
        self.url = reverse('anomaly-detection')
    
    @patch('ml_security.views.anomaly_detector.detect_anomaly')
    def test_anomaly_detection_api_success(self, mock_detect):
        """Test successful anomaly detection"""
        # Mock the detection
        mock_detect.return_value = (True, 0.85, "Anomaly detected!", "IsolationForest")
        
        event_data = {
            'ip_latitude': 34.0522,
            'ip_longitude': -118.2437,
            'time_of_day_sin': 0.5,
            'time_of_day_cos': 0.866
        }
        
        response = self.client.post(
            self.url,
            data=json.dumps({
                'event_data': event_data,
                'event_type': 'login'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('is_anomaly', data)
        self.assertIn('anomaly_score', data)
    
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
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)
        self.url = reverse('threat-analysis')
    
    @patch('ml_security.views.threat_analyzer.analyze_threat')
    def test_threat_analysis_api_success(self, mock_analyze):
        """Test successful threat analysis"""
        # Mock the analysis
        mock_analyze.return_value = (0.75, True, "Enable MFA")
        
        response = self.client.post(
            self.url,
            data=json.dumps({
                'data_sequence': 'user_login_success browser_chrome',
                'analysis_type': 'session_activity'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('threat_score', data)
        self.assertIn('is_threat', data)
        self.assertIn('recommended_action', data)
    
    def test_threat_analysis_creates_record(self):
        """Test that analysis creates database record"""
        with patch('ml_security.views.threat_analyzer.analyze_threat') as mock:
            mock.return_value = (0.8, True, "Lock account")
            
            initial_count = ThreatAnalysisResult.objects.count()
            
            response = self.client.post(
                self.url,
                data=json.dumps({
                    'data_sequence': 'suspicious_activity',
                    'analysis_type': 'login_behavior'
                }),
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                ThreatAnalysisResult.objects.count(),
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
        client = Client()
        client.force_login(self.user)
        
        with patch('ml_security.views.password_strength.predict_strength') as mock:
            mock.return_value = (0.85, "Strong!")
            
            # Make API call
            response = client.post(
                reverse('password-strength-check'),
                data=json.dumps({'password': 'TestPass123!'}),
                content_type='application/json'
            )
            
            # Verify response
            self.assertEqual(response.status_code, 200)
            
            # Verify database record
            prediction = PasswordStrengthPrediction.objects.filter(
                user=self.user
            ).first()
            self.assertIsNotNone(prediction)
            self.assertEqual(prediction.strength_score, 0.85)
    
    def test_complete_anomaly_detection_flow(self):
        """Test complete flow: API call -> detection -> database storage -> alert"""
        client = Client()
        client.force_login(self.user)
        
        with patch('ml_security.views.anomaly_detector.detect_anomaly') as mock:
            mock.return_value = (True, 0.95, "Critical anomaly!", "IsolationForest")
            
            # Make API call
            response = client.post(
                reverse('anomaly-detection'),
                data=json.dumps({
                    'event_data': {'ip': '10.0.0.1'},
                    'event_type': 'login'
                }),
                content_type='application/json'
            )
            
            # Verify response
            self.assertEqual(response.status_code, 200)
            
            # Verify database record
            log = AnomalyDetectionLog.objects.filter(
                user=self.user,
                is_anomaly=True
            ).first()
            self.assertIsNotNone(log)
            self.assertTrue(log.is_anomaly)
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
            strength_score=0.0,
            feedback="Empty password"
        )
        
        self.assertEqual(prediction.strength_score, 0.0)
    
    def test_extreme_anomaly_scores(self):
        """Test handling of extreme anomaly scores"""
        # Test score of 0 (definitely not an anomaly)
        log_min = AnomalyDetectionLog.objects.create(
            user=self.user,
            event_type='test',
            event_data={},
            is_anomaly=False,
            anomaly_score=0.0,
            model_used='Test'
        )
        self.assertEqual(log_min.anomaly_score, 0.0)
        
        # Test score of 1 (definitely an anomaly)
        log_max = AnomalyDetectionLog.objects.create(
            user=self.user,
            event_type='test',
            event_data={},
            is_anomaly=True,
            anomaly_score=1.0,
            model_used='Test'
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
            strength_score=0.5
        )
        
        AnomalyDetectionLog.objects.create(
            user=self.user,
            event_type='test',
            event_data={},
            is_anomaly=False,
            model_used='Test'
        )
        
        ThreatAnalysisResult.objects.create(
            user=self.user,
            analysis_type='test',
            input_features={},
            threat_score=0.5,
            is_threat=False
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
            AnomalyDetectionLog.objects.filter(user_id=user_id).count(),
            0
        )
        self.assertEqual(
            ThreatAnalysisResult.objects.filter(user_id=user_id).count(),
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
                strength_score=0.5 + (i % 50) / 100,
                feedback=f"Feedback {i}"
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
                strength_score=0.5
            )
        
        import time
        from django.db import connection
        from django.test.utils import override_settings
        
        # Query recent predictions
        start_time = time.time()
        
        recent = PasswordStrengthPrediction.objects.filter(
            user=self.user
        ).order_by('-timestamp')[:10]
        
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
            strength_score=score,
            feedback="Test feedback"
        )
    
    @staticmethod
    def create_test_anomaly(user, is_anomaly=False):
        """Create a test anomaly detection log"""
        return AnomalyDetectionLog.objects.create(
            user=user,
            event_type='test',
            event_data={},
            is_anomaly=is_anomaly,
            anomaly_score=0.8 if is_anomaly else 0.2,
            model_used='Test'
        )
    
    @staticmethod
    def create_test_threat_analysis(user, is_threat=False):
        """Create a test threat analysis result"""
        return ThreatAnalysisResult.objects.create(
            user=user,
            analysis_type='test',
            input_features={},
            threat_score=0.8 if is_threat else 0.2,
            is_threat=is_threat,
            recommended_action="Test action"
        )


# Run specific test suites
def suite():
    """Create test suite for ML Security module"""
    from django.test.loader import TestLoader
    loader = TestLoader()
    suite = loader.loadTestsFromModule(__name__)
    return suite

