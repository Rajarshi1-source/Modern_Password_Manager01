# ML Models for Dark Web Monitoring

This directory stores trained ML models for the dark web breach detection system.

## Directory Structure

```
ml_models/dark_web/
├── breach_classifier/          # BERT-based breach classifier
│   ├── config.json            # Model configuration
│   ├── pytorch_model.bin      # Model weights
│   ├── tokenizer_config.json  # Tokenizer config
│   └── vocab.txt              # Vocabulary
├── credential_matcher.pth      # Siamese network for credential matching
└── README.md                   # This file
```

## Models

### 1. Breach Classifier (BERT-based)

**Purpose**: Classify dark web content as breach/non-breach and assign severity

**Architecture**:
- Base Model: DistilBERT (distilbert-base-uncased)
- Task: Sequence Classification (4 classes)
- Classes: LOW, MEDIUM, HIGH, CRITICAL
- Max Sequence Length: 512 tokens

**Training**:
```bash
python manage.py shell
>>> from ml_dark_web.training.train_breach_classifier import train_model
>>> train_model(num_samples=10000, epochs=50)
```

**Location**: `breach_classifier/`

**Files**:
- `config.json` - Model architecture configuration
- `pytorch_model.bin` - Trained weights (large file, ~250MB)
- `tokenizer_config.json` - Tokenizer settings
- `vocab.txt` - BERT vocabulary

### 2. Credential Matcher (Siamese Neural Network)

**Purpose**: Fuzzy matching of user credentials against breach data

**Architecture**:
- Input: SHA-256 email hashes (256 bytes)
- Hidden layers: 512 → 256 → 128 (embedding dimension)
- Activation: ReLU with Dropout (0.3)
- Output: 128-dimensional embedding
- Similarity: Cosine similarity

**Training**:
```bash
# Training script coming soon
# For now, using untrained initialization
```

**Location**: `credential_matcher.pth`

**File**: PyTorch state dict (~2MB)

## Model Storage

### Development

Models are stored locally in this directory.

### Production

**Recommended**: Store models in cloud storage:
- AWS S3
- Google Cloud Storage
- Azure Blob Storage

**Environment variables**:
```python
ML_MODELS_PATH = os.environ.get('ML_MODELS_PATH', 'ml_models/')
```

## Loading Models

Models are loaded automatically by `ml_services.py`:

```python
from ml_dark_web.ml_services import BreachClassifier, CredentialMatcherService

# Load breach classifier
classifier = BreachClassifier()

# Load credential matcher
matcher = CredentialMatcherService()
```

## Model Performance

### Breach Classifier

Expected metrics (after training):
- **Accuracy**: 85-90%
- **Precision**: 80-85%
- **Recall**: 85-90%
- **F1 Score**: 82-87%

### Credential Matcher

Expected metrics:
- **True Positive Rate**: > 95% (similarity > 0.85)
- **False Positive Rate**: < 5%
- **Average Match Time**: < 100ms per credential

## Model Versioning

Track model versions in `MLModelMetadata` model:

```python
from ml_dark_web.models import MLModelMetadata

MLModelMetadata.objects.create(
    model_name='breach_classifier',
    version='1.0',
    accuracy=0.87,
    f1_score=0.84,
    precision=0.82,
    recall=0.86,
    model_path='ml_models/dark_web/breach_classifier/'
)
```

## Model Updates

### Updating Breach Classifier

1. Train new model:
   ```bash
   python manage.py train_breach_classifier --epochs 100
   ```

2. Backup old model:
   ```bash
   mv breach_classifier breach_classifier_v1.0_backup
   ```

3. Copy new model to this directory

4. Update metadata in database

5. Restart Django/Celery workers

### Updating Credential Matcher

1. Train new Siamese network
2. Save state dict: `torch.save(model.state_dict(), 'credential_matcher_v2.pth')`
3. Update `ML_CONFIG.SIAMESE_MODEL_PATH`
4. Restart workers

## Monitoring

Monitor model performance via Django admin:
- Go to `/admin/ml_dark_web/mlmodelmetadata/`
- View accuracy, precision, recall, F1 score
- Track last training date
- Compare versions

## Troubleshooting

### Model Not Found Error

```python
# Error: FileNotFoundError: Model not found
```

**Solution**:
1. Check `ML_CONFIG.MODELS_DIR` path
2. Verify model files exist
3. Check file permissions
4. For first run, models will use default HuggingFace downloads

### Out of Memory Error

```python
# Error: CUDA out of memory
```

**Solution**:
1. Reduce `ML_CONFIG.BATCH_SIZE`
2. Use CPU: `ML_CONFIG.DEVICE = 'cpu'`
3. Use smaller model (e.g., distilbert instead of bert-base)

### Slow Inference

**Solutions**:
1. Use GPU if available
2. Batch predictions
3. Cache frequently checked credentials
4. Consider model quantization

## Security

### Model File Security

- **Don't commit large model files to Git**
- Use Git LFS for model versioning
- Store production models in secure cloud storage
- Encrypt model files at rest
- Use IAM/access controls

### Model Poisoning Prevention

- Validate training data sources
- Monitor model outputs for anomalies
- Regular model retraining
- A/B test new models before deployment

## Resources

- **BERT Paper**: https://arxiv.org/abs/1810.04805
- **Siamese Networks**: https://www.cs.cmu.edu/~rsalakhu/papers/oneshot1.pdf
- **HuggingFace Transformers**: https://huggingface.co/docs/transformers/
- **PyTorch**: https://pytorch.org/docs/

---

**Created**: 2025-01-24
**Last Updated**: 2025-01-24
**Version**: 1.0.0

