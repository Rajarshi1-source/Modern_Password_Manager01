# ML Models Directory

This directory stores all trained machine learning models used by the Password Manager.

## Structure

```
ml_models/
├── dark_web/              # Dark web monitoring models
│   ├── breach_classifier/ # BERT-based breach detection
│   ├── credential_matcher.pth # Siamese network
│   └── README.md
├── password_strength/     # Password strength prediction (LSTM)
│   └── lstm_model.h5
└── anomaly_detection/     # Session anomaly detection
    └── autoencoder.pth
```

## Model Types

### 1. Dark Web Monitoring (`dark_web/`)

**Models**:
- **Breach Classifier**: BERT-based NLP model for detecting breaches in scraped content
- **Credential Matcher**: Siamese Neural Network for fuzzy credential matching

**Size**: ~250MB (BERT) + ~2MB (Siamese)

**See**: `dark_web/README.md` for details

### 2. Password Strength (`password_strength/`)

**Model**: LSTM-based password strength predictor

**Architecture**:
- Input: Character sequences (max length 64)
- LSTM layers: 128 → 64 units
- Output: 5 classes (very_weak to very_strong)

**Size**: ~5MB

**Training**: Via `ml_security/training/train_password_strength.py`

### 3. Anomaly Detection (`anomaly_detection/`)

**Model**: Autoencoder for session behavior analysis

**Architecture**:
- Encoder: 32 → 16 → 8 dimensions
- Decoder: 8 → 16 → 32 dimensions
- Reconstruction error threshold: 0.5

**Size**: ~1MB

**Purpose**: Detect suspicious session patterns

## Git LFS Setup

Large model files should use Git LFS:

```bash
# Install Git LFS
git lfs install

# Track model files
git lfs track "*.bin"
git lfs track "*.pth"
git lfs track "*.h5"

# Commit .gitattributes
git add .gitattributes
git commit -m "Configure Git LFS for model files"
```

## Cloud Storage (Production)

For production, store models in cloud storage:

### AWS S3

```python
# settings.py
ML_MODELS_STORAGE = 's3://your-bucket/ml_models/'
```

### Google Cloud Storage

```python
# settings.py
ML_MODELS_STORAGE = 'gs://your-bucket/ml_models/'
```

### Azure Blob Storage

```python
# settings.py
ML_MODELS_STORAGE = 'https://account.blob.core.windows.net/ml_models/'
```

## Model Management

### List All Models

```bash
python manage.py shell
>>> from ml_dark_web.models import MLModelMetadata
>>> MLModelMetadata.objects.all()
```

### Update Model

1. Train new version
2. Save to this directory
3. Update metadata in database
4. Restart Django/Celery workers

### Backup Models

```bash
# Backup all models
tar -czf ml_models_backup_$(date +%Y%m%d).tar.gz ml_models/

# Upload to cloud
aws s3 cp ml_models_backup_*.tar.gz s3://backups/ml_models/
```

## Performance Monitoring

Track model performance in Django admin:
- `/admin/ml_security/mlmodelmetadata/`
- `/admin/ml_dark_web/mlmodelmetadata/`

## Security

- ✅ Don't commit large model files to Git
- ✅ Use Git LFS for version control
- ✅ Encrypt models in cloud storage
- ✅ Use IAM/access controls
- ✅ Regular security audits
- ✅ Monitor for model poisoning

## Resources

- **TensorFlow**: https://www.tensorflow.org/
- **PyTorch**: https://pytorch.org/
- **HuggingFace**: https://huggingface.co/
- **Git LFS**: https://git-lfs.github.com/

---

**Last Updated**: 2025-01-24

