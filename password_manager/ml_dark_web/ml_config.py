"""
ML Models Configuration for Dark Web Monitoring
"""

import torch
from pathlib import Path
from django.conf import settings


class MLDarkWebConfig:
    """Configuration for ML models used in dark web monitoring"""
    
    # Directories
    BASE_DIR = Path(__file__).resolve().parent.parent
    MODELS_DIR = BASE_DIR / 'ml_models' / 'dark_web'
    DATA_DIR = BASE_DIR / 'ml_data' / 'dark_web'
    TRAINING_DATA_DIR = DATA_DIR / 'training'
    
    # Ensure directories exist
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TRAINING_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # BERT Breach Classifier Configuration
    BERT_MODEL_NAME = 'distilbert-base-uncased'  # Faster, lighter than BERT
    BERT_MODEL_PATH = MODELS_DIR / 'breach_classifier'
    BERT_MAX_LENGTH = 512
    BERT_NUM_LABELS = 4  # LOW, MEDIUM, HIGH, CRITICAL
    BERT_DROPOUT = 0.3
    
    # Siamese Network Configuration
    SIAMESE_MODEL_PATH = MODELS_DIR / 'credential_matcher.pth'
    SIAMESE_EMBEDDING_DIM = 128
    SIAMESE_INPUT_DIM = 256  # Hash representation dimension
    SIAMESE_HIDDEN_DIMS = [512, 256]
    SIAMESE_DROPOUT = 0.3
    
    # LSTM Pattern Detector Configuration
    LSTM_MODEL_PATH = MODELS_DIR / 'pattern_detector.pth'
    LSTM_INPUT_DIM = 64
    LSTM_HIDDEN_DIM = 128
    LSTM_NUM_LAYERS = 2
    LSTM_DROPOUT = 0.2
    LSTM_SEQUENCE_LENGTH = 30  # Days
    
    # NER Entity Extractor (spaCy)
    NER_MODEL_NAME = 'en_core_web_sm'
    
    # Training Configuration
    BATCH_SIZE = 32
    LEARNING_RATE = 2e-5
    NUM_EPOCHS = 10
    WARMUP_STEPS = 500
    WEIGHT_DECAY = 0.01
    
    # Thresholds
    BREACH_CONFIDENCE_THRESHOLD = 0.75  # Minimum confidence to classify as breach
    SIMILARITY_THRESHOLD = 0.85  # Minimum similarity for credential match
    PATTERN_CONFIDENCE_THRESHOLD = 0.70  # Minimum confidence for pattern detection
    
    # Processing
    DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
    MAX_WORKERS = 4  # For parallel processing
    
    # Scraping Configuration
    TOR_PROXY = getattr(settings, 'TOR_PROXY', 'socks5h://localhost:9050')
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    REQUEST_TIMEOUT = 30
    RETRY_ATTEMPTS = 3
    SCRAPE_DELAY_SECONDS = 5  # Delay between requests
    
    # Dark Web Sources (Example - add more as needed)
    MONITORED_SOURCES = [
        {
            'name': 'Breach Forums (Archive)',
            'url': 'example.onion',  # Replace with actual onion addresses
            'type': 'forum',
            'reliability': 0.8
        },
        # Add more sources as needed
    ]
    
    # Feature Engineering
    EMBEDDING_SIZE = 256  # For credential embeddings
    HASH_ALGORITHM = 'sha256'
    
    # Celery Task Configuration
    SCRAPE_SCHEDULE_HOURS = 24  # How often to scrape sources
    MATCH_BATCH_SIZE = 1000  # Credentials to match per batch
    ANALYSIS_PRIORITY = 'high'  # Celery task priority
    
    # Performance Optimization
    ENABLE_CACHING = True
    CACHE_TIMEOUT_SECONDS = 3600  # 1 hour
    ENABLE_BATCH_PROCESSING = True
    
    # Logging
    LOG_LEVEL = 'INFO'
    ENABLE_DETAILED_LOGGING = True
    
    # PostgreSQL pgvector Configuration
    PGVECTOR_DIMENSIONS = 768  # BERT embedding dimensions
    PGVECTOR_LISTS = 100  # IVFFlat index lists
    PGVECTOR_PROBES = 10  # Search probes
    
    # Model Versioning
    CURRENT_MODEL_VERSION = '1.0.0'
    MODEL_REGISTRY = {
        'breach_classifier': '1.0.0',
        'credential_matcher': '1.0.0',
        'pattern_detector': '1.0.0',
    }
    
    # Severity Mapping
    SEVERITY_LEVELS = {
        0: 'LOW',
        1: 'MEDIUM',
        2: 'HIGH',
        3: 'CRITICAL'
    }
    
    # Alert Thresholds
    ALERT_THRESHOLDS = {
        'LOW': 0.75,
        'MEDIUM': 0.80,
        'HIGH': 0.85,
        'CRITICAL': 0.90
    }
    
    @classmethod
    def get_device_info(cls):
        """Get device information for ML models"""
        return {
            'device': cls.DEVICE,
            'cuda_available': torch.cuda.is_available(),
            'cuda_device_count': torch.cuda.device_count() if torch.cuda.is_available() else 0,
            'cuda_device_name': torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'
        }
    
    @classmethod
    def validate_config(cls):
        """Validate configuration"""
        issues = []
        
        # Check if model directories exist
        if not cls.MODELS_DIR.exists():
            issues.append(f"Models directory not found: {cls.MODELS_DIR}")
        
        # Check if training data directory exists
        if not cls.TRAINING_DATA_DIR.exists():
            issues.append(f"Training data directory not found: {cls.TRAINING_DATA_DIR}")
        
        # Check CUDA availability if specified
        if cls.DEVICE == 'cuda' and not torch.cuda.is_available():
            issues.append("CUDA specified but not available. Falling back to CPU.")
            cls.DEVICE = 'cpu'
        
        return issues if issues else None


# Severity configuration for breach classification
SEVERITY_CONFIG = {
    'LOW': {
        'score_range': (0.0, 0.25),
        'color': '#FFA500',
        'priority': 1,
        'notify_immediately': False
    },
    'MEDIUM': {
        'score_range': (0.25, 0.50),
        'color': '#FF8C00',
        'priority': 2,
        'notify_immediately': False
    },
    'HIGH': {
        'score_range': (0.50, 0.75),
        'color': '#FF4500',
        'priority': 3,
        'notify_immediately': True
    },
    'CRITICAL': {
        'score_range': (0.75, 1.0),
        'color': '#DC143C',
        'priority': 4,
        'notify_immediately': True
    }
}


# Data preprocessing configuration
PREPROCESSING_CONFIG = {
    'lowercase': True,
    'remove_urls': True,
    'remove_emails_from_text': False,  # Keep for extraction
    'remove_special_chars': False,
    'max_text_length': 10000,
    'truncation': True,
}

