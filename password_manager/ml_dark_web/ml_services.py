"""
ML Service Layer for Dark Web Monitoring
Implements BERT Classifier and Siamese Network for credential matching
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForSequenceClassification, AutoConfig
import numpy as np
from typing import List, Dict, Tuple, Optional
import hashlib
import logging
from pathlib import Path

from .ml_config import MLDarkWebConfig

logger = logging.getLogger(__name__)


class BreachClassifierService:
    """
    BERT-based breach detection classifier
    Uses DistilBERT for efficient text classification
    """
    
    def __init__(self, model_path: Optional[Path] = None):
        self.device = MLDarkWebConfig.DEVICE
        self.config = MLDarkWebConfig
        self.tokenizer = None
        self.model = None
        
        # Initialize model
        self._load_model(model_path)
    
    def _load_model(self, model_path: Optional[Path] = None):
        """Load or initialize BERT model"""
        try:
            model_path = model_path or self.config.BERT_MODEL_PATH
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.config.BERT_MODEL_NAME,
                cache_dir=self.config.MODELS_DIR
            )
            
            # Try to load fine-tuned model
            if model_path.exists():
                logger.info(f"Loading fine-tuned model from {model_path}")
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    model_path,
                    num_labels=self.config.BERT_NUM_LABELS
                )
            else:
                logger.warning(f"Fine-tuned model not found at {model_path}. Using base model.")
                # Load base model for fine-tuning
                config = AutoConfig.from_pretrained(
                    self.config.BERT_MODEL_NAME,
                    num_labels=self.config.BERT_NUM_LABELS,
                    hidden_dropout_prob=self.config.BERT_DROPOUT,
                    attention_probs_dropout_prob=self.config.BERT_DROPOUT
                )
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    self.config.BERT_MODEL_NAME,
                    config=config,
                    cache_dir=self.config.MODELS_DIR
                )
            
            self.model.to(self.device)
            self.model.eval()
            logger.info(f"Model loaded successfully on {self.device}")
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise
    
    def preprocess_text(self, text: str) -> str:
        """Preprocess text before classification"""
        # Basic preprocessing
        text = text.strip()
        
        # Truncate if too long
        if len(text) > self.config.PREPROCESSING_CONFIG['max_text_length']:
            text = text[:self.config.PREPROCESSING_CONFIG['max_text_length']]
        
        return text
    
    def classify_breach(self, text: str) -> Dict[str, any]:
        """
        Classify if text contains breach information
        
        Args:
            text: Text content to classify
            
        Returns:
            dict: {
                'is_breach': bool,
                'severity': str,
                'confidence': float,
                'probabilities': dict
            }
        """
        try:
            # Preprocess
            text = self.preprocess_text(text)
            
            # Tokenize
            inputs = self.tokenizer(
                text,
                max_length=self.config.BERT_MAX_LENGTH,
                padding='max_length',
                truncation=True,
                return_tensors='pt'
            ).to(self.device)
            
            # Predict
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                probabilities = torch.softmax(logits, dim=-1)
                predicted_class = torch.argmax(probabilities, dim=-1).item()
                confidence = probabilities[0][predicted_class].item()
            
            # Map to severity
            severity = self.config.SEVERITY_LEVELS[predicted_class]
            
            # Get all probabilities
            prob_dict = {
                self.config.SEVERITY_LEVELS[i]: probabilities[0][i].item()
                for i in range(self.config.BERT_NUM_LABELS)
            }
            
            # Determine if it's a breach based on confidence threshold
            is_breach = confidence >= self.config.BREACH_CONFIDENCE_THRESHOLD
            
            return {
                'is_breach': is_breach,
                'severity': severity,
                'confidence': confidence,
                'probabilities': prob_dict,
                'predicted_class': predicted_class
            }
            
        except Exception as e:
            logger.error(f"Error classifying breach: {e}")
            return {
                'is_breach': False,
                'severity': 'LOW',
                'confidence': 0.0,
                'probabilities': {},
                'error': str(e)
            }
    
    def batch_classify(self, texts: List[str]) -> List[Dict]:
        """
        Batch classification for efficiency
        
        Args:
            texts: List of texts to classify
            
        Returns:
            list: List of classification results
        """
        results = []
        batch_size = self.config.BATCH_SIZE
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_results = [self.classify_breach(text) for text in batch]
            results.extend(batch_results)
            
            logger.info(f"Processed batch {i // batch_size + 1}/{(len(texts) // batch_size) + 1}")
        
        return results
    
    def extract_breach_indicators(self, text: str) -> Dict[str, List[str]]:
        """
        Extract breach indicators from text using regex patterns
        
        Returns:
            dict: {
                'emails': list,
                'domains': list,
                'credentials': list,
                'dates': list
            }
        """
        import re
        
        indicators = {
            'emails': [],
            'domains': [],
            'credentials': [],
            'dates': []
        }
        
        # Extract emails
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        indicators['emails'] = re.findall(email_pattern, text)
        
        # Extract domains
        domain_pattern = r'\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9][a-z0-9-]{0,61}[a-z0-9]\b'
        indicators['domains'] = list(set(re.findall(domain_pattern, text.lower())))
        
        # Extract dates (various formats)
        date_pattern = r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b|\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b'
        indicators['dates'] = re.findall(date_pattern, text)
        
        # Extract potential credentials (email:password format)
        credential_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}:[^\s]+\b'
        indicators['credentials'] = re.findall(credential_pattern, text)
        
        return indicators


class SiameseCredentialMatcher(nn.Module):
    """
    Siamese Neural Network for credential matching
    Uses twin networks with shared weights for similarity computation
    """
    
    def __init__(self, 
                 input_dim=256, 
                 embedding_dim=128, 
                 hidden_dims=[512, 256],
                 dropout=0.3):
        super().__init__()
        
        self.input_dim = input_dim
        self.embedding_dim = embedding_dim
        
        # Build embedding network
        layers = []
        current_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(current_dim, hidden_dim),
                nn.ReLU(),
                nn.BatchNorm1d(hidden_dim),
                nn.Dropout(dropout)
            ])
            current_dim = hidden_dim
        
        # Final embedding layer
        layers.append(nn.Linear(current_dim, embedding_dim))
        
        self.embedding = nn.Sequential(*layers)
    
    def forward_one(self, x):
        """Forward pass for one input"""
        return self.embedding(x)
    
    def forward(self, x1, x2):
        """Forward pass for both inputs"""
        out1 = self.forward_one(x1)
        out2 = self.forward_one(x2)
        return out1, out2
    
    def compute_similarity(self, emb1, emb2):
        """Compute cosine similarity between embeddings"""
        return F.cosine_similarity(emb1, emb2, dim=-1)


class CredentialMatcherService:
    """Service for matching credentials against breaches using Siamese network"""
    
    def __init__(self, model_path: Optional[Path] = None):
        self.device = MLDarkWebConfig.DEVICE
        self.config = MLDarkWebConfig
        
        # Initialize Siamese network
        self.model = SiameseCredentialMatcher(
            input_dim=self.config.SIAMESE_INPUT_DIM,
            embedding_dim=self.config.SIAMESE_EMBEDDING_DIM,
            hidden_dims=self.config.SIAMESE_HIDDEN_DIMS,
            dropout=self.config.SIAMESE_DROPOUT
        )
        
        # Load trained weights if available
        self._load_model(model_path)
        
        self.model.to(self.device)
        self.model.eval()
    
    def _load_model(self, model_path: Optional[Path] = None):
        """Load trained Siamese model"""
        model_path = model_path or self.config.SIAMESE_MODEL_PATH
        
        if model_path.exists():
            try:
                logger.info(f"Loading Siamese model from {model_path}")
                self.model.load_state_dict(
                    torch.load(model_path, map_location=self.device)
                )
                logger.info("Siamese model loaded successfully")
            except Exception as e:
                logger.warning(f"Could not load Siamese model: {e}. Using untrained model.")
        else:
            logger.warning(f"Siamese model not found at {model_path}. Using untrained model.")
    
    def hash_credential(self, credential: str, algorithm='sha256') -> str:
        """Create secure hash of credential"""
        hash_func = hashlib.new(algorithm)
        hash_func.update(credential.lower().strip().encode('utf-8'))
        return hash_func.hexdigest()
    
    def credential_to_vector(self, credential_hash: str) -> torch.Tensor:
        """
        Convert credential hash to vector representation
        Uses hash bytes as features
        """
        try:
            # Convert hex hash to bytes
            hash_bytes = bytes.fromhex(credential_hash)
            
            # Convert to numpy array
            vector = np.frombuffer(hash_bytes, dtype=np.uint8).astype(np.float32)
            
            # Normalize to [0, 1]
            vector = vector / 255.0
            
            # Pad or truncate to input_dim
            if len(vector) < self.config.SIAMESE_INPUT_DIM:
                vector = np.pad(
                    vector, 
                    (0, self.config.SIAMESE_INPUT_DIM - len(vector)), 
                    'constant'
                )
            elif len(vector) > self.config.SIAMESE_INPUT_DIM:
                vector = vector[:self.config.SIAMESE_INPUT_DIM]
            
            # Convert to tensor
            return torch.tensor(vector, dtype=torch.float32).to(self.device)
            
        except Exception as e:
            logger.error(f"Error converting credential to vector: {e}")
            # Return zero vector as fallback
            return torch.zeros(self.config.SIAMESE_INPUT_DIM, dtype=torch.float32).to(self.device)
    
    def calculate_similarity(self, cred1_hash: str, cred2_hash: str) -> float:
        """
        Calculate similarity between two credential hashes
        
        Args:
            cred1_hash: First credential hash
            cred2_hash: Second credential hash
            
        Returns:
            float: Similarity score (0-1)
        """
        try:
            vec1 = self.credential_to_vector(cred1_hash).unsqueeze(0)
            vec2 = self.credential_to_vector(cred2_hash).unsqueeze(0)
            
            with torch.no_grad():
                emb1, emb2 = self.model(vec1, vec2)
                similarity = self.model.compute_similarity(emb1, emb2).item()
            
            # Convert from [-1, 1] to [0, 1]
            similarity = (similarity + 1) / 2
            
            return similarity
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0
    
    def find_matches(self, 
                     user_credential_hash: str, 
                     breach_credentials: List[str],
                     threshold: Optional[float] = None) -> List[Tuple[str, float]]:
        """
        Find matching credentials in breach data
        
        Args:
            user_credential_hash: User's credential hash to check
            breach_credentials: List of breach credentials (plaintext or hashed)
            threshold: Similarity threshold (default from config)
            
        Returns:
            list: List of (credential, similarity_score) tuples
        """
        threshold = threshold or self.config.SIMILARITY_THRESHOLD
        matches = []
        
        for breach_cred in breach_credentials:
            # Hash breach credential if not already hashed
            if len(breach_cred) != 64:  # Not a SHA-256 hash
                breach_hash = self.hash_credential(breach_cred)
            else:
                breach_hash = breach_cred
            
            # Calculate similarity
            similarity = self.calculate_similarity(user_credential_hash, breach_hash)
            
            # Add to matches if above threshold
            if similarity >= threshold:
                matches.append((breach_cred, similarity))
        
        # Sort by similarity (descending)
        matches.sort(key=lambda x: x[1], reverse=True)
        
        return matches
    
    def batch_find_matches(self,
                          user_credentials: List[str],
                          breach_credentials: List[str],
                          threshold: Optional[float] = None) -> Dict[str, List[Tuple[str, float]]]:
        """
        Batch matching for multiple user credentials
        
        Returns:
            dict: {user_credential: [(breach_credential, similarity), ...]}
        """
        results = {}
        threshold = threshold or self.config.SIMILARITY_THRESHOLD
        
        for user_cred in user_credentials:
            user_hash = self.hash_credential(user_cred)
            matches = self.find_matches(user_hash, breach_credentials, threshold)
            if matches:
                results[user_cred] = matches
        
        return results
    
    def get_embedding(self, credential_hash: str) -> np.ndarray:
        """
        Get embedding vector for a credential
        Useful for storing in database for similarity search
        """
        try:
            vec = self.credential_to_vector(credential_hash).unsqueeze(0)
            
            with torch.no_grad():
                embedding = self.model.forward_one(vec)
            
            return embedding.cpu().numpy().flatten()
            
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            return np.zeros(self.config.SIAMESE_EMBEDDING_DIM)


# Initialize global instances for reuse
_breach_classifier = None
_credential_matcher = None


def get_breach_classifier() -> BreachClassifierService:
    """Get singleton breach classifier instance"""
    global _breach_classifier
    if _breach_classifier is None:
        _breach_classifier = BreachClassifierService()
    return _breach_classifier


def get_credential_matcher() -> CredentialMatcherService:
    """Get singleton credential matcher instance"""
    global _credential_matcher
    if _credential_matcher is None:
        _credential_matcher = CredentialMatcherService()
    return _credential_matcher

