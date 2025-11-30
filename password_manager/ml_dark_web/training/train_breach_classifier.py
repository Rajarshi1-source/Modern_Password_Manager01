"""
Training Script for BERT-based Breach Classifier
Fine-tunes DistilBERT for breach detection
"""

import os
import sys
import django
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModelForSequenceClassification, AdamW
from transformers import get_linear_schedule_with_warmup
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
import numpy as np
from tqdm import tqdm
import logging

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'password_manager.settings')
django.setup()

from ml_dark_web.ml_config import MLDarkWebConfig
from ml_dark_web.models import MLModelMetadata

logger = logging.getLogger(__name__)


class BreachDataset(Dataset):
    """PyTorch Dataset for breach classification"""
    
    def __init__(self, texts, labels, tokenizer, max_length=512):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self):
        return len(self.texts)
    
    def __getitem__(self, idx):
        text = str(self.texts[idx])
        label = self.labels[idx]
        
        encoding = self.tokenizer.encode_plus(
            text,
            add_special_tokens=True,
            max_length=self.max_length,
            return_token_type_ids=False,
            padding='max_length',
            truncation=True,
            return_attention_mask=True,
            return_tensors='pt'
        )
        
        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(label, dtype=torch.long)
        }


def generate_synthetic_training_data(num_samples=10000):
    """
    Generate synthetic training data for breach classification
    In production, replace with real labeled data
    
    Returns:
        texts: List of text samples
        labels: List of labels (0=LOW, 1=MEDIUM, 2=HIGH, 3=CRITICAL)
    """
    import random
    
    texts = []
    labels = []
    
    # Templates for different severity levels
    templates = {
        0: [  # LOW
            "User database backup available",
            "Old forum posts archive",
            "Public email list compilation",
        ],
        1: [  # MEDIUM
            "Database dump contains {} user records with emails",
            "Leaked customer list from {}",
            "Compromised user accounts: {} entries",
        ],
        2: [  # HIGH
            "BREACH: {} database leaked with passwords",
            "Major data breach at {} - {} million users affected",
            "Urgent: {} credentials exposed including passwords and emails",
        ],
        3: [  # CRITICAL
            "CRITICAL BREACH: {} full database dump with plaintext passwords",
            "Massive leak: {} million users, passwords, SSN, credit cards",
            "URGENT: {} complete user database including financial data",
        ]
    }
    
    companies = ["TechCorp", "DataServices", "SocialHub", "CloudSystem", "WebStore"]
    
    for _ in range(num_samples):
        severity = random.choice([0, 1, 2, 3])
        template = random.choice(templates[severity])
        
        # Fill in template
        if '{}' in template:
            company = random.choice(companies)
            count = random.randint(1000, 10000000)
            text = template.format(company) if template.count('{}') == 1 else template.format(company, count)
        else:
            text = template
        
        # Add some noise
        if random.random() > 0.7:
            text += f" Posted on {random.choice(['forum', 'telegram', 'darkweb marketplace'])}"
        
        texts.append(text)
        labels.append(severity)
    
    return texts, labels


def train_model(num_samples=10000, epochs=10, batch_size=16, save_model=True):
    """
    Train the breach classifier model
    
    Args:
        num_samples: Number of training samples
        epochs: Number of training epochs
        batch_size: Batch size for training
        save_model: Whether to save the trained model
    """
    print("=" * 80)
    print("BERT BREACH CLASSIFIER TRAINING")
    print("=" * 80)
    print()
    
    # Set device
    device = MLDarkWebConfig.DEVICE
    print(f"Using device: {device}")
    print()
    
    # Load tokenizer and model
    print("Loading DistilBERT tokenizer and model...")
    tokenizer = AutoTokenizer.from_pretrained(MLDarkWebConfig.BERT_MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MLDarkWebConfig.BERT_MODEL_NAME,
        num_labels=MLDarkWebConfig.BERT_NUM_LABELS
    )
    model.to(device)
    print("Model loaded successfully")
    print()
    
    # Generate training data
    print(f"Generating {num_samples} training samples...")
    texts, labels = generate_synthetic_training_data(num_samples)
    
    # Split data
    train_texts, val_texts, train_labels, val_labels = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )
    
    print(f"Training samples: {len(train_texts)}")
    print(f"Validation samples: {len(val_texts)}")
    print()
    
    # Create datasets
    train_dataset = BreachDataset(train_texts, train_labels, tokenizer)
    val_dataset = BreachDataset(val_texts, val_labels, tokenizer)
    
    # Create dataloaders
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size)
    
    # Optimizer and scheduler
    optimizer = AdamW(model.parameters(), lr=MLDarkWebConfig.LEARNING_RATE)
    total_steps = len(train_loader) * epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=MLDarkWebConfig.WARMUP_STEPS,
        num_training_steps=total_steps
    )
    
    # Training loop
    print("Starting training...")
    print()
    
    best_val_accuracy = 0
    
    for epoch in range(epochs):
        print(f"Epoch {epoch + 1}/{epochs}")
        print("-" * 40)
        
        # Training
        model.train()
        train_loss = 0
        train_preds = []
        train_labels_list = []
        
        for batch in tqdm(train_loader, desc="Training"):
            optimizer.zero_grad()
            
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels_batch = batch['labels'].to(device)
            
            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels_batch
            )
            
            loss = outputs.loss
            train_loss += loss.item()
            
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            
            preds = torch.argmax(outputs.logits, dim=1)
            train_preds.extend(preds.cpu().numpy())
            train_labels_list.extend(labels_batch.cpu().numpy())
        
        # Calculate training metrics
        avg_train_loss = train_loss / len(train_loader)
        train_accuracy = accuracy_score(train_labels_list, train_preds)
        
        print(f"  Train Loss: {avg_train_loss:.4f}")
        print(f"  Train Accuracy: {train_accuracy:.4f}")
        
        # Validation
        model.eval()
        val_loss = 0
        val_preds = []
        val_labels_list = []
        
        with torch.no_grad():
            for batch in tqdm(val_loader, desc="Validation"):
                input_ids = batch['input_ids'].to(device)
                attention_mask = batch['attention_mask'].to(device)
                labels_batch = batch['labels'].to(device)
                
                outputs = model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=labels_batch
                )
                
                val_loss += outputs.loss.item()
                
                preds = torch.argmax(outputs.logits, dim=1)
                val_preds.extend(preds.cpu().numpy())
                val_labels_list.extend(labels_batch.cpu().numpy())
        
        # Calculate validation metrics
        avg_val_loss = val_loss / len(val_loader)
        val_accuracy = accuracy_score(val_labels_list, val_preds)
        precision, recall, f1, _ = precision_recall_fscore_support(
            val_labels_list, val_preds, average='weighted'
        )
        
        print(f"  Val Loss: {avg_val_loss:.4f}")
        print(f"  Val Accuracy: {val_accuracy:.4f}")
        print(f"  Val Precision: {precision:.4f}")
        print(f"  Val Recall: {recall:.4f}")
        print(f"  Val F1: {f1:.4f}")
        print()
        
        # Save best model
        if val_accuracy > best_val_accuracy:
            best_val_accuracy = val_accuracy
            if save_model:
                model_path = MLDarkWebConfig.BERT_MODEL_PATH
                model_path.mkdir(parents=True, exist_ok=True)
                model.save_pretrained(model_path)
                tokenizer.save_pretrained(model_path)
                print(f"✓ Model saved to {model_path}")
                print()
    
    print("=" * 80)
    print("TRAINING COMPLETED!")
    print(f"Best Validation Accuracy: {best_val_accuracy:.4f}")
    print("=" * 80)
    
    # Save metadata to database
    if save_model:
        try:
            MLModelMetadata.objects.update_or_create(
                model_type='breach_classifier',
                version=MLDarkWebConfig.CURRENT_MODEL_VERSION,
                defaults={
                    'file_path': str(MLDarkWebConfig.BERT_MODEL_PATH),
                    'accuracy': best_val_accuracy,
                    'precision': precision,
                    'recall': recall,
                    'f1_score': f1,
                    'training_samples': num_samples,
                    'hyperparameters': {
                        'epochs': epochs,
                        'batch_size': batch_size,
                        'learning_rate': MLDarkWebConfig.LEARNING_RATE,
                        'max_length': MLDarkWebConfig.BERT_MAX_LENGTH
                    },
                    'is_active': True,
                    'notes': f'DistilBERT fine-tuned on {num_samples} samples'
                }
            )
            print("✓ Model metadata saved to database")
        except Exception as e:
            print(f"Warning: Could not save metadata to database: {e}")
    
    return model, tokenizer


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Train BERT Breach Classifier')
    parser.add_argument('--samples', type=int, default=10000, help='Number of training samples')
    parser.add_argument('--epochs', type=int, default=10, help='Number of training epochs')
    parser.add_argument('--batch-size', type=int, default=16, help='Training batch size')
    parser.add_argument('--no-save', action='store_true', help='Do not save the model')
    
    args = parser.parse_args()
    
    try:
        train_model(
            num_samples=args.samples,
            epochs=args.epochs,
            batch_size=args.batch_size,
            save_model=not args.no_save
        )
    except KeyboardInterrupt:
        print("\n\nTraining interrupted by user.")
    except Exception as e:
        print(f"\n\nError during training: {str(e)}")
        import traceback
        traceback.print_exc()

