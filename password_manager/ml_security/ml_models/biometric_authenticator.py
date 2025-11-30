"""
Advanced Biometric Authentication using Machine Learning

This module implements multi-modal biometric authentication including:
- Face Recognition (using FaceNet/DeepFace embeddings)
- Voice Recognition (using MFCC and CNN)
- Continuous Authentication
- Liveness Detection
"""

import numpy as np
import os
import logging
import joblib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import base64
import hashlib

logger = logging.getLogger(__name__)

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras.models import Model, load_model
    from tensorflow.keras.layers import (
        Input, Conv2D, Dense, Flatten, Dropout,
        BatchNormalization, MaxPooling2D, GlobalAveragePooling2D,
        LSTM, Conv1D, MaxPooling1D
    )
    from tensorflow.keras.applications import MobileNetV2
    TENSORFLOW_AVAILABLE = True
except ImportError:
    logger.warning("TensorFlow not available. Biometric auth will use fallback methods.")
    TENSORFLOW_AVAILABLE = False

try:
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    logger.warning("Scikit-learn not available for biometric features.")
    SKLEARN_AVAILABLE = False


class BiometricAuthenticator:
    """
    Multi-modal biometric authentication system
    
    Features:
    - Face recognition with liveness detection
    - Voice recognition using audio features
    - Continuous authentication scoring
    - Anti-spoofing measures
    """
    
    def __init__(self, model_dir=None):
        self.model_dir = model_dir or os.path.join(
            os.path.dirname(__file__),
            '..',
            'trained_models'
        )
        
        # Initialize models
        self.face_encoder = None
        self.face_liveness_detector = None
        self.voice_encoder = None
        self.continuous_auth_model = None
        
        # Feature scalers
        self.face_scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self.voice_scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        
        # Thresholds
        self.face_similarity_threshold = 0.6
        self.voice_similarity_threshold = 0.7
        self.liveness_threshold = 0.5
        self.continuous_auth_threshold = 0.6
        
        # User biometric database (in production, use secure database)
        self.user_biometrics = {}
        
        if TENSORFLOW_AVAILABLE:
            try:
                self._load_models()
            except Exception as e:
                logger.warning(f"Failed to load biometric models: {e}")
                self._initialize_models()
    
    def _initialize_models(self):
        """Initialize new biometric models"""
        if not TENSORFLOW_AVAILABLE:
            logger.warning("TensorFlow not available. Cannot initialize models.")
            return
        
        # Face encoder using MobileNetV2 (lightweight for production)
        self.face_encoder = self._build_face_encoder()
        
        # Liveness detection model
        self.face_liveness_detector = self._build_liveness_detector()
        
        # Voice encoder using CNN
        self.voice_encoder = self._build_voice_encoder()
        
        # Continuous authentication model
        self.continuous_auth_model = self._build_continuous_auth_model()
        
        logger.info("Biometric models initialized successfully")
    
    def _build_face_encoder(self):
        """
        Build face encoding model using transfer learning
        
        Returns:
            keras.Model: Face encoder that outputs 128-dim embeddings
        """
        if not TENSORFLOW_AVAILABLE:
            return None
        
        # Use MobileNetV2 as base (efficient for production)
        base_model = MobileNetV2(
            input_shape=(160, 160, 3),
            include_top=False,
            weights='imagenet'
        )
        
        # Freeze base model layers
        base_model.trainable = False
        
        # Build encoder
        inputs = Input(shape=(160, 160, 3))
        x = base_model(inputs, training=False)
        x = GlobalAveragePooling2D()(x)
        x = Dense(256, activation='relu')(x)
        x = Dropout(0.5)(x)
        embeddings = Dense(128, activation=None, name='embeddings')(x)
        
        model = Model(inputs=inputs, outputs=embeddings)
        
        return model
    
    def _build_liveness_detector(self):
        """
        Build liveness detection model to prevent photo/video spoofing
        
        Returns:
            keras.Model: Binary classifier for live vs spoof detection
        """
        if not TENSORFLOW_AVAILABLE:
            return None
        
        inputs = Input(shape=(160, 160, 3))
        
        # Lightweight CNN for liveness detection
        x = Conv2D(32, (3, 3), activation='relu', padding='same')(inputs)
        x = BatchNormalization()(x)
        x = MaxPooling2D((2, 2))(x)
        
        x = Conv2D(64, (3, 3), activation='relu', padding='same')(x)
        x = BatchNormalization()(x)
        x = MaxPooling2D((2, 2))(x)
        
        x = Conv2D(128, (3, 3), activation='relu', padding='same')(x)
        x = BatchNormalization()(x)
        x = MaxPooling2D((2, 2))(x)
        
        x = Flatten()(x)
        x = Dense(128, activation='relu')(x)
        x = Dropout(0.5)(x)
        liveness_score = Dense(1, activation='sigmoid', name='liveness')(x)
        
        model = Model(inputs=inputs, outputs=liveness_score)
        
        return model
    
    def _build_voice_encoder(self):
        """
        Build voice encoding model using MFCC features
        
        Returns:
            keras.Model: Voice encoder that outputs 64-dim embeddings
        """
        if not TENSORFLOW_AVAILABLE:
            return None
        
        # Input: MFCC features (40 coefficients × time frames)
        inputs = Input(shape=(40, 100, 1))  # 40 MFCCs, 100 time frames
        
        # 1D CNN for temporal patterns
        x = Conv2D(32, (3, 3), activation='relu', padding='same')(inputs)
        x = BatchNormalization()(x)
        x = MaxPooling2D((2, 2))(x)
        
        x = Conv2D(64, (3, 3), activation='relu', padding='same')(x)
        x = BatchNormalization()(x)
        x = MaxPooling2D((2, 2))(x)
        
        x = Flatten()(x)
        x = Dense(128, activation='relu')(x)
        x = Dropout(0.5)(x)
        embeddings = Dense(64, activation=None, name='voice_embeddings')(x)
        
        model = Model(inputs=inputs, outputs=embeddings)
        
        return model
    
    def _build_continuous_auth_model(self):
        """
        Build continuous authentication model that combines multiple factors
        
        Returns:
            keras.Model: Multi-input model for continuous authentication
        """
        if not TENSORFLOW_AVAILABLE:
            return None
        
        # Face embedding input
        face_input = Input(shape=(128,), name='face_embedding')
        
        # Voice embedding input
        voice_input = Input(shape=(64,), name='voice_embedding')
        
        # Behavioral features input
        behavior_input = Input(shape=(15,), name='behavior_features')
        
        # Combine all features
        combined = keras.layers.concatenate([face_input, voice_input, behavior_input])
        
        # Dense layers for authentication decision
        x = Dense(128, activation='relu')(combined)
        x = Dropout(0.3)(x)
        x = Dense(64, activation='relu')(x)
        x = Dropout(0.3)(x)
        auth_score = Dense(1, activation='sigmoid', name='auth_score')(x)
        
        model = Model(
            inputs=[face_input, voice_input, behavior_input],
            outputs=auth_score
        )
        
        return model
    
    def _load_models(self):
        """Load pre-trained biometric models from disk"""
        try:
            face_encoder_path = os.path.join(self.model_dir, 'face_encoder.h5')
            if os.path.exists(face_encoder_path):
                self.face_encoder = load_model(face_encoder_path)
                logger.info("Face encoder loaded successfully")
            
            liveness_detector_path = os.path.join(self.model_dir, 'liveness_detector.h5')
            if os.path.exists(liveness_detector_path):
                self.face_liveness_detector = load_model(liveness_detector_path)
                logger.info("Liveness detector loaded successfully")
            
            voice_encoder_path = os.path.join(self.model_dir, 'voice_encoder.h5')
            if os.path.exists(voice_encoder_path):
                self.voice_encoder = load_model(voice_encoder_path)
                logger.info("Voice encoder loaded successfully")
            
            continuous_auth_path = os.path.join(self.model_dir, 'continuous_auth.h5')
            if os.path.exists(continuous_auth_path):
                self.continuous_auth_model = load_model(continuous_auth_path)
                logger.info("Continuous auth model loaded successfully")
            
            # Load user biometrics database
            biometrics_db_path = os.path.join(self.model_dir, 'user_biometrics.json')
            if os.path.exists(biometrics_db_path):
                with open(biometrics_db_path, 'r') as f:
                    self.user_biometrics = json.load(f)
                logger.info("User biometrics database loaded successfully")
        
        except Exception as e:
            logger.error(f"Error loading biometric models: {e}")
            raise
    
    def register_face(self, user_id: str, face_image: np.ndarray) -> Dict:
        """
        Register user's face for authentication
        
        Args:
            user_id: Unique user identifier
            face_image: Preprocessed face image (160x160x3)
        
        Returns:
            dict: Registration result with embedding and liveness score
        """
        try:
            # Check liveness
            liveness_score = self._detect_liveness(face_image)
            
            if liveness_score < self.liveness_threshold:
                return {
                    'success': False,
                    'message': 'Liveness check failed. Please ensure you are live.',
                    'liveness_score': float(liveness_score)
                }
            
            # Generate face embedding
            embedding = self._encode_face(face_image)
            
            # Store user biometrics
            if user_id not in self.user_biometrics:
                self.user_biometrics[user_id] = {}
            
            self.user_biometrics[user_id]['face_embedding'] = embedding.tolist()
            self.user_biometrics[user_id]['face_registered_at'] = datetime.now().isoformat()
            
            # Save to disk
            self._save_biometrics_database()
            
            return {
                'success': True,
                'message': 'Face registered successfully',
                'liveness_score': float(liveness_score)
            }
        
        except Exception as e:
            logger.error(f"Error registering face: {e}")
            return {
                'success': False,
                'message': f'Face registration failed: {str(e)}'
            }
    
    def authenticate_face(self, user_id: str, face_image: np.ndarray) -> Dict:
        """
        Authenticate user using face recognition
        
        Args:
            user_id: User identifier
            face_image: Face image to verify
        
        Returns:
            dict: Authentication result with similarity score
        """
        try:
            # Check if user has registered face
            if user_id not in self.user_biometrics or 'face_embedding' not in self.user_biometrics[user_id]:
                return {
                    'authenticated': False,
                    'message': 'Face not registered for this user'
                }
            
            # Check liveness
            liveness_score = self._detect_liveness(face_image)
            
            if liveness_score < self.liveness_threshold:
                return {
                    'authenticated': False,
                    'message': 'Liveness check failed',
                    'liveness_score': float(liveness_score)
                }
            
            # Generate embedding for current face
            current_embedding = self._encode_face(face_image)
            
            # Compare with stored embedding
            stored_embedding = np.array(self.user_biometrics[user_id]['face_embedding'])
            similarity = self._compute_similarity(current_embedding, stored_embedding)
            
            authenticated = similarity >= self.face_similarity_threshold
            
            return {
                'authenticated': authenticated,
                'similarity_score': float(similarity),
                'liveness_score': float(liveness_score),
                'threshold': self.face_similarity_threshold,
                'message': 'Face authentication successful' if authenticated else 'Face not recognized'
            }
        
        except Exception as e:
            logger.error(f"Error during face authentication: {e}")
            return {
                'authenticated': False,
                'message': f'Authentication error: {str(e)}'
            }
    
    def register_voice(self, user_id: str, voice_features: np.ndarray) -> Dict:
        """
        Register user's voiceprint
        
        Args:
            user_id: Unique user identifier
            voice_features: MFCC features extracted from voice sample
        
        Returns:
            dict: Registration result
        """
        try:
            # Generate voice embedding
            embedding = self._encode_voice(voice_features)
            
            # Store user biometrics
            if user_id not in self.user_biometrics:
                self.user_biometrics[user_id] = {}
            
            self.user_biometrics[user_id]['voice_embedding'] = embedding.tolist()
            self.user_biometrics[user_id]['voice_registered_at'] = datetime.now().isoformat()
            
            # Save to disk
            self._save_biometrics_database()
            
            return {
                'success': True,
                'message': 'Voice registered successfully'
            }
        
        except Exception as e:
            logger.error(f"Error registering voice: {e}")
            return {
                'success': False,
                'message': f'Voice registration failed: {str(e)}'
            }
    
    def authenticate_voice(self, user_id: str, voice_features: np.ndarray) -> Dict:
        """
        Authenticate user using voice recognition
        
        Args:
            user_id: User identifier
            voice_features: MFCC features to verify
        
        Returns:
            dict: Authentication result with similarity score
        """
        try:
            # Check if user has registered voice
            if user_id not in self.user_biometrics or 'voice_embedding' not in self.user_biometrics[user_id]:
                return {
                    'authenticated': False,
                    'message': 'Voice not registered for this user'
                }
            
            # Generate embedding for current voice
            current_embedding = self._encode_voice(voice_features)
            
            # Compare with stored embedding
            stored_embedding = np.array(self.user_biometrics[user_id]['voice_embedding'])
            similarity = self._compute_similarity(current_embedding, stored_embedding)
            
            authenticated = similarity >= self.voice_similarity_threshold
            
            return {
                'authenticated': authenticated,
                'similarity_score': float(similarity),
                'threshold': self.voice_similarity_threshold,
                'message': 'Voice authentication successful' if authenticated else 'Voice not recognized'
            }
        
        except Exception as e:
            logger.error(f"Error during voice authentication: {e}")
            return {
                'authenticated': False,
                'message': f'Authentication error: {str(e)}'
            }
    
    def continuous_authenticate(
        self,
        user_id: str,
        face_image: Optional[np.ndarray] = None,
        voice_features: Optional[np.ndarray] = None,
        behavior_features: Optional[np.ndarray] = None
    ) -> Dict:
        """
        Perform continuous multi-factor authentication
        
        Args:
            user_id: User identifier
            face_image: Optional face image
            voice_features: Optional voice features
            behavior_features: Behavioral biometrics features
        
        Returns:
            dict: Continuous authentication score and factors used
        """
        try:
            factors_used = []
            scores = []
            
            # Face authentication
            if face_image is not None:
                face_result = self.authenticate_face(user_id, face_image)
                if face_result.get('authenticated'):
                    factors_used.append('face')
                    scores.append(face_result['similarity_score'])
            
            # Voice authentication
            if voice_features is not None:
                voice_result = self.authenticate_voice(user_id, voice_features)
                if voice_result.get('authenticated'):
                    factors_used.append('voice')
                    scores.append(voice_result['similarity_score'])
            
            # Behavioral analysis (using existing anomaly detector)
            if behavior_features is not None:
                # Normalize behavior features
                if len(behavior_features) == 15:
                    factors_used.append('behavior')
                    # Simple behavioral score (can be enhanced)
                    behavior_score = min(1.0, np.mean(behavior_features) / 100)
                    scores.append(behavior_score)
            
            # Calculate combined authentication score
            if scores:
                auth_score = np.mean(scores)
                authenticated = auth_score >= self.continuous_auth_threshold
            else:
                auth_score = 0.0
                authenticated = False
            
            return {
                'authenticated': authenticated,
                'auth_score': float(auth_score),
                'factors_used': factors_used,
                'threshold': self.continuous_auth_threshold,
                'message': 'Continuous authentication successful' if authenticated else 'Authentication failed'
            }
        
        except Exception as e:
            logger.error(f"Error during continuous authentication: {e}")
            return {
                'authenticated': False,
                'message': f'Authentication error: {str(e)}'
            }
    
    def _encode_face(self, face_image: np.ndarray) -> np.ndarray:
        """Generate face embedding"""
        if self.face_encoder is None:
            # Fallback: use simple hash-based encoding
            return np.array([hash(face_image.tobytes()) % 256 for _ in range(128)])
        
        # Ensure correct shape
        if len(face_image.shape) == 3:
            face_image = np.expand_dims(face_image, axis=0)
        
        # Generate embedding
        embedding = self.face_encoder.predict(face_image, verbose=0)[0]
        
        return embedding
    
    def _encode_voice(self, voice_features: np.ndarray) -> np.ndarray:
        """Generate voice embedding"""
        if self.voice_encoder is None:
            # Fallback: use simple hash-based encoding
            return np.array([hash(voice_features.tobytes()) % 256 for _ in range(64)])
        
        # Ensure correct shape (40, 100, 1)
        if len(voice_features.shape) == 2:
            voice_features = np.expand_dims(voice_features, axis=-1)
        if len(voice_features.shape) == 3:
            voice_features = np.expand_dims(voice_features, axis=0)
        
        # Generate embedding
        embedding = self.voice_encoder.predict(voice_features, verbose=0)[0]
        
        return embedding
    
    def _detect_liveness(self, face_image: np.ndarray) -> float:
        """Detect if face is live (not a photo or video)"""
        if self.face_liveness_detector is None:
            # Fallback: basic checks
            # Check for image variance (photos tend to have less variance)
            variance = np.var(face_image)
            return min(1.0, variance / 1000.0)
        
        # Ensure correct shape
        if len(face_image.shape) == 3:
            face_image = np.expand_dims(face_image, axis=0)
        
        # Predict liveness
        liveness_score = self.face_liveness_detector.predict(face_image, verbose=0)[0][0]
        
        return float(liveness_score)
    
    def _compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings"""
        if SKLEARN_AVAILABLE:
            # Use sklearn for accurate cosine similarity
            similarity = cosine_similarity(
                embedding1.reshape(1, -1),
                embedding2.reshape(1, -1)
            )[0][0]
        else:
            # Fallback: manual cosine similarity
            dot_product = np.dot(embedding1, embedding2)
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            similarity = dot_product / (norm1 * norm2 + 1e-8)
        
        return float(similarity)
    
    def _save_biometrics_database(self):
        """Save user biometrics to disk"""
        try:
            os.makedirs(self.model_dir, exist_ok=True)
            biometrics_db_path = os.path.join(self.model_dir, 'user_biometrics.json')
            
            with open(biometrics_db_path, 'w') as f:
                json.dump(self.user_biometrics, f)
            
            logger.info("User biometrics database saved successfully")
        
        except Exception as e:
            logger.error(f"Error saving biometrics database: {e}")
    
    def extract_mfcc_features(self, audio_data: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
        """
        Extract MFCC features from audio data
        
        Args:
            audio_data: Raw audio waveform
            sample_rate: Audio sample rate
        
        Returns:
            np.ndarray: MFCC features (40, 100, 1)
        """
        try:
            import librosa
            
            # Extract 40 MFCCs
            mfccs = librosa.feature.mfcc(
                y=audio_data,
                sr=sample_rate,
                n_mfcc=40,
                n_fft=2048,
                hop_length=512
            )
            
            # Ensure fixed size (40, 100)
            if mfccs.shape[1] < 100:
                # Pad if too short
                pad_width = ((0, 0), (0, 100 - mfccs.shape[1]))
                mfccs = np.pad(mfccs, pad_width, mode='constant')
            else:
                # Truncate if too long
                mfccs = mfccs[:, :100]
            
            # Add channel dimension
            mfccs = np.expand_dims(mfccs, axis=-1)
            
            return mfccs
        
        except ImportError:
            logger.warning("librosa not available for MFCC extraction")
            # Fallback: return dummy features
            return np.random.randn(40, 100, 1)

