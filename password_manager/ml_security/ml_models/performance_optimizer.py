"""
ML Performance Optimizer
========================
Machine Learning model for:
- Performance prediction
- Anomaly detection
- Optimization recommendations
- Resource allocation

Author: Password Manager Team
Date: October 2025
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib
from datetime import datetime, timedelta
from django.conf import settings
from django.db.models import Avg, Count, Max, Min
import os
import logging

logger = logging.getLogger(__name__)


class PerformanceOptimizer:
    """
    ML-based performance optimizer for predicting and optimizing application performance.
    """
    
    def __init__(self):
        self.model_dir = os.path.join(settings.BASE_DIR, 'ml_security', 'saved_models')
        os.makedirs(self.model_dir, exist_ok=True)
        
        # Models
        self.response_time_predictor = None
        self.anomaly_detector = None
        self.scaler = StandardScaler()
        
        # Model paths
        self.predictor_path = os.path.join(self.model_dir, 'response_time_predictor.pkl')
        self.anomaly_path = os.path.join(self.model_dir, 'performance_anomaly_detector.pkl')
        self.scaler_path = os.path.join(self.model_dir, 'performance_scaler.pkl')
        
        # Load models if they exist
        self.load_models()
    
    def load_models(self):
        """Load trained models from disk."""
        try:
            if os.path.exists(self.predictor_path):
                self.response_time_predictor = joblib.load(self.predictor_path)
                logger.info("✅ Response time predictor loaded")
            
            if os.path.exists(self.anomaly_path):
                self.anomaly_detector = joblib.load(self.anomaly_path)
                logger.info("✅ Anomaly detector loaded")
            
            if os.path.exists(self.scaler_path):
                self.scaler = joblib.load(self.scaler_path)
                logger.info("✅ Scaler loaded")
        except Exception as e:
            logger.error(f"Error loading performance models: {e}")
    
    def save_models(self):
        """Save trained models to disk."""
        try:
            if self.response_time_predictor:
                joblib.dump(self.response_time_predictor, self.predictor_path)
            
            if self.anomaly_detector:
                joblib.dump(self.anomaly_detector, self.anomaly_path)
            
            joblib.dump(self.scaler, self.scaler_path)
            
            logger.info("✅ Performance models saved successfully")
        except Exception as e:
            logger.error(f"Error saving performance models: {e}")
    
    def prepare_training_data(self, days_back=30):
        """
        Prepare training data from performance metrics.
        
        Args:
            days_back: Number of days of historical data to use
            
        Returns:
            X: Feature matrix
            y: Target variable (response time)
        """
        from shared.models import PerformanceMetric, SystemMetric
        
        # Get performance metrics
        cutoff_date = datetime.now() - timedelta(days=days_back)
        metrics = PerformanceMetric.objects.filter(
            timestamp__gte=cutoff_date
        ).select_related('user')
        
        if metrics.count() < 100:
            logger.warning(f"Insufficient data for training: {metrics.count()} samples")
            return None, None
        
        data = []
        for metric in metrics:
            # Extract features
            features = {
                'hour_of_day': metric.timestamp.hour,
                'day_of_week': metric.timestamp.weekday(),
                'query_count': metric.query_count or 0,
                'query_time': metric.query_time or 0,
                'memory_usage': metric.memory_usage or 0,
                'is_authenticated': 1 if metric.user else 0,
                'method_GET': 1 if metric.method == 'GET' else 0,
                'method_POST': 1 if metric.method == 'POST' else 0,
                'method_PUT': 1 if metric.method == 'PUT' else 0,
                'method_DELETE': 1 if metric.method == 'DELETE' else 0,
                'path_length': len(metric.path),
                'response_time': metric.duration,
            }
            
            # Get corresponding system metrics
            system_metric = SystemMetric.objects.filter(
                timestamp__gte=metric.timestamp - timedelta(minutes=1),
                timestamp__lte=metric.timestamp + timedelta(minutes=1)
            ).first()
            
            if system_metric:
                features['cpu_usage'] = system_metric.cpu_usage
                features['memory_percent'] = system_metric.memory_percent
                features['disk_usage'] = system_metric.disk_usage
            else:
                features['cpu_usage'] = 0
                features['memory_percent'] = 0
                features['disk_usage'] = 0
            
            data.append(features)
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Separate features and target
        X = df.drop('response_time', axis=1)
        y = df['response_time']
        
        return X, y
    
    def train_response_time_predictor(self, X=None, y=None):
        """
        Train Random Forest model to predict response times.
        
        Args:
            X: Feature matrix (optional, will be generated if not provided)
            y: Target variable (optional, will be generated if not provided)
        """
        if X is None or y is None:
            X, y = self.prepare_training_data()
        
        if X is None or len(X) < 100:
            logger.error("Insufficient data for training response time predictor")
            return False
        
        try:
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train model
            self.response_time_predictor = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                random_state=42,
                n_jobs=-1
            )
            
            self.response_time_predictor.fit(X_train_scaled, y_train)
            
            # Evaluate
            train_score = self.response_time_predictor.score(X_train_scaled, y_train)
            test_score = self.response_time_predictor.score(X_test_scaled, y_test)
            
            logger.info(f"✅ Response time predictor trained - Train R²: {train_score:.3f}, Test R²: {test_score:.3f}")
            
            # Save models
            self.save_models()
            
            return True
        except Exception as e:
            logger.error(f"Error training response time predictor: {e}")
            return False
    
    def train_anomaly_detector(self, X=None, y=None):
        """
        Train Isolation Forest for performance anomaly detection.
        
        Args:
            X: Feature matrix (optional, will be generated if not provided)
            y: Target variable (unused, for compatibility)
        """
        if X is None:
            X, _ = self.prepare_training_data()
        
        if X is None or len(X) < 100:
            logger.error("Insufficient data for training anomaly detector")
            return False
        
        try:
            # Scale features
            X_scaled = self.scaler.fit_transform(X)
            
            # Train Isolation Forest
            self.anomaly_detector = IsolationForest(
                n_estimators=100,
                contamination=0.1,  # 10% of data expected to be anomalies
                random_state=42,
                n_jobs=-1
            )
            
            self.anomaly_detector.fit(X_scaled)
            
            # Test predictions
            predictions = self.anomaly_detector.predict(X_scaled)
            anomaly_count = sum(predictions == -1)
            anomaly_percent = (anomaly_count / len(predictions)) * 100
            
            logger.info(f"✅ Anomaly detector trained - Detected {anomaly_count} anomalies ({anomaly_percent:.2f}%)")
            
            # Save models
            self.save_models()
            
            return True
        except Exception as e:
            logger.error(f"Error training anomaly detector: {e}")
            return False
    
    def predict_response_time(self, features):
        """
        Predict response time for given features.
        
        Args:
            features: Dictionary of feature values
            
        Returns:
            Predicted response time in milliseconds
        """
        if not self.response_time_predictor:
            logger.warning("Response time predictor not trained")
            return None
        
        try:
            # Convert features to DataFrame
            df = pd.DataFrame([features])
            
            # Scale features
            X_scaled = self.scaler.transform(df)
            
            # Predict
            prediction = self.response_time_predictor.predict(X_scaled)[0]
            
            return max(0, prediction)  # Ensure non-negative
        except Exception as e:
            logger.error(f"Error predicting response time: {e}")
            return None
    
    def detect_anomaly(self, features):
        """
        Detect if given features represent a performance anomaly.
        
        Args:
            features: Dictionary of feature values
            
        Returns:
            is_anomaly: Boolean indicating if this is an anomaly
            anomaly_score: Anomaly score (lower is more anomalous)
        """
        if not self.anomaly_detector:
            logger.warning("Anomaly detector not trained")
            return False, 0.0
        
        try:
            # Convert features to DataFrame
            df = pd.DataFrame([features])
            
            # Scale features
            X_scaled = self.scaler.transform(df)
            
            # Predict
            prediction = self.anomaly_detector.predict(X_scaled)[0]
            score = self.anomaly_detector.score_samples(X_scaled)[0]
            
            is_anomaly = prediction == -1
            
            return is_anomaly, score
        except Exception as e:
            logger.error(f"Error detecting anomaly: {e}")
            return False, 0.0
    
    def get_feature_importance(self):
        """
        Get feature importance from the response time predictor.
        
        Returns:
            Dictionary of feature names and their importance scores
        """
        if not self.response_time_predictor:
            return {}
        
        try:
            # Get feature names (this should match the order in prepare_training_data)
            feature_names = [
                'hour_of_day', 'day_of_week', 'query_count', 'query_time',
                'memory_usage', 'is_authenticated', 'method_GET', 'method_POST',
                'method_PUT', 'method_DELETE', 'path_length', 'cpu_usage',
                'memory_percent', 'disk_usage'
            ]
            
            importances = self.response_time_predictor.feature_importances_
            
            return dict(zip(feature_names, importances))
        except Exception as e:
            logger.error(f"Error getting feature importance: {e}")
            return {}
    
    def generate_optimization_recommendations(self):
        """
        Generate optimization recommendations based on performance data.
        
        Returns:
            List of recommendation dictionaries
        """
        from shared.models import PerformanceMetric, APIPerformanceMetric
        
        recommendations = []
        
        try:
            # Get recent performance data
            cutoff = datetime.now() - timedelta(days=7)
            
            # 1. Identify slow endpoints
            slow_endpoints = APIPerformanceMetric.objects.filter(
                timestamp__gte=cutoff
            ).values('endpoint').annotate(
                avg_time=Avg('response_time'),
                request_count=Count('id')
            ).filter(
                avg_time__gt=1000  # > 1 second
            ).order_by('-avg_time')[:5]
            
            for endpoint in slow_endpoints:
                recommendations.append({
                    'type': 'SLOW_ENDPOINT',
                    'severity': 'HIGH' if endpoint['avg_time'] > 2000 else 'MEDIUM',
                    'title': f"Slow endpoint detected: {endpoint['endpoint']}",
                    'description': f"Average response time: {endpoint['avg_time']:.0f}ms over {endpoint['request_count']} requests",
                    'suggestion': "Consider caching, query optimization, or async processing"
                })
            
            # 2. Identify high query count endpoints
            high_query_endpoints = PerformanceMetric.objects.filter(
                timestamp__gte=cutoff,
                query_count__gt=50
            ).values('path').annotate(
                avg_queries=Avg('query_count'),
                request_count=Count('id')
            ).order_by('-avg_queries')[:5]
            
            for endpoint in high_query_endpoints:
                recommendations.append({
                    'type': 'HIGH_QUERY_COUNT',
                    'severity': 'HIGH' if endpoint['avg_queries'] > 100 else 'MEDIUM',
                    'title': f"N+1 query issue: {endpoint['path']}",
                    'description': f"Average {endpoint['avg_queries']:.0f} queries per request over {endpoint['request_count']} requests",
                    'suggestion': "Use select_related() or prefetch_related() to optimize queries"
                })
            
            # 3. Memory usage analysis
            high_memory = PerformanceMetric.objects.filter(
                timestamp__gte=cutoff,
                memory_usage__gt=100  # > 100 MB
            ).values('path').annotate(
                avg_memory=Avg('memory_usage'),
                max_memory=Max('memory_usage'),
                request_count=Count('id')
            ).order_by('-avg_memory')[:5]
            
            for endpoint in high_memory:
                recommendations.append({
                    'type': 'HIGH_MEMORY_USAGE',
                    'severity': 'MEDIUM',
                    'title': f"High memory usage: {endpoint['path']}",
                    'description': f"Average {endpoint['avg_memory']:.1f}MB, Peak {endpoint['max_memory']:.1f}MB",
                    'suggestion': "Consider pagination, lazy loading, or data streaming"
                })
            
            # 4. Error rate analysis
            from shared.models import ErrorLog
            
            error_patterns = ErrorLog.objects.filter(
                timestamp__gte=cutoff,
                resolved=False
            ).values('error_type').annotate(
                error_count=Count('id')
            ).order_by('-error_count')[:5]
            
            for pattern in error_patterns:
                recommendations.append({
                    'type': 'HIGH_ERROR_RATE',
                    'severity': 'HIGH' if pattern['error_count'] > 100 else 'MEDIUM',
                    'title': f"Frequent error: {pattern['error_type']}",
                    'description': f"{pattern['error_count']} occurrences in the last 7 days",
                    'suggestion': "Review error logs and implement fixes or better error handling"
                })
            
            # 5. Feature importance recommendations
            if self.response_time_predictor:
                importance = self.get_feature_importance()
                top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:3]
                
                recommendations.append({
                    'type': 'PERFORMANCE_INSIGHTS',
                    'severity': 'LOW',
                    'title': "Top performance impact factors",
                    'description': f"Most influential: {', '.join([f[0] for f in top_features])}",
                    'suggestion': "Focus optimization efforts on these areas for maximum impact"
                })
            
            logger.info(f"Generated {len(recommendations)} optimization recommendations")
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
        
        return recommendations
    
    def train_all_models(self):
        """
        Train all performance optimization models.
        
        Returns:
            Dictionary with training results
        """
        results = {
            'response_time_predictor': False,
            'anomaly_detector': False,
            'timestamp': datetime.now().isoformat()
        }
        
        # Prepare data once
        X, y = self.prepare_training_data()
        
        if X is None or len(X) < 100:
            logger.error("Insufficient data for training")
            return results
        
        # Train response time predictor
        if self.train_response_time_predictor(X, y):
            results['response_time_predictor'] = True
        
        # Train anomaly detector
        if self.train_anomaly_detector(X, y):
            results['anomaly_detector'] = True
        
        return results


# Global instance
performance_optimizer = PerformanceOptimizer()

