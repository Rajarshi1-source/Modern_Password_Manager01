"""
Training Script for Password Strength LSTM Model

This script trains the LSTM neural network for password strength prediction.
"""

import os
import sys
import django
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'password_manager.settings')
django.setup()

from ml_security.ml_models.password_strength import PasswordStrengthPredictor
from ml_security.models import MLModelMetadata

def generate_training_data(num_samples=10000):
    """
    Generate synthetic training data for password strength prediction
    
    Returns:
        passwords: List of password strings
        labels: List of strength labels
    """
    import random
    import string
    
    passwords = []
    labels = []
    
    # Character sets
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special = '!@#$%^&*()_+-=[]{}|;:,.<>?'
    
    for _ in range(num_samples):
        # Randomly choose password strength to generate
        strength = random.choice(['very_weak', 'weak', 'moderate', 'strong', 'very_strong'])
        
        if strength == 'very_weak':
            # Short, simple passwords
            length = random.randint(4, 7)
            chars = random.choice([lowercase, digits])
            password = ''.join(random.choice(chars) for _ in range(length))
        
        elif strength == 'weak':
            # Short passwords with limited character variety
            length = random.randint(6, 9)
            char_sets = random.choice([
                lowercase + digits,
                lowercase + uppercase,
                uppercase + digits
            ])
            password = ''.join(random.choice(char_sets) for _ in range(length))
        
        elif strength == 'moderate':
            # Medium length with some variety
            length = random.randint(8, 11)
            char_sets = lowercase + uppercase + digits
            if random.random() > 0.5:
                char_sets += special[:len(special)//2]
            password = ''.join(random.choice(char_sets) for _ in range(length))
        
        elif strength == 'strong':
            # Good length with variety
            length = random.randint(10, 14)
            char_sets = lowercase + uppercase + digits + special
            password = ''.join(random.choice(char_sets) for _ in range(length))
        
        else:  # very_strong
            # Long with high entropy
            length = random.randint(14, 25)
            char_sets = lowercase + uppercase + digits + special
            password = ''.join(random.choice(char_sets) for _ in range(length))
            # Ensure variety
            if not any(c in uppercase for c in password):
                password = password[:length//2] + random.choice(uppercase) + password[length//2+1:]
            if not any(c in digits for c in password):
                password = password[:length//3] + random.choice(digits) + password[length//3+1:]
            if not any(c in special for c in password):
                password = password[:length//4] + random.choice(special) + password[length//4+1:]
        
        passwords.append(password)
        labels.append(strength)
    
    return passwords, labels


def prepare_labels(labels, strength_classes):
    """
    Convert labels to one-hot encoded format
    
    Args:
        labels: List of strength labels
        strength_classes: List of class names
    
    Returns:
        One-hot encoded labels
    """
    label_encoder = LabelEncoder()
    label_encoder.classes_ = np.array(strength_classes)
    
    encoded = label_encoder.transform(labels)
    
    # One-hot encode
    one_hot = np.zeros((len(encoded), len(strength_classes)))
    one_hot[np.arange(len(encoded)), encoded] = 1
    
    return one_hot


def train_model(num_samples=10000, epochs=50, batch_size=32):
    """
    Train the password strength LSTM model
    
    Args:
        num_samples: Number of training samples to generate
        epochs: Number of training epochs
        batch_size: Batch size for training
    """
    print("=" * 80)
    print("PASSWORD STRENGTH LSTM MODEL TRAINING")
    print("=" * 80)
    print()
    
    # Initialize model
    print("Initializing Password Strength Predictor...")
    predictor = PasswordStrengthPredictor()
    
    # Generate training data
    print(f"Generating {num_samples} training samples...")
    passwords, labels = generate_training_data(num_samples)
    
    # Split data
    print("Splitting data into train/test sets (80/20)...")
    train_passwords, test_passwords, train_labels, test_labels = train_test_split(
        passwords, labels, test_size=0.2, random_state=42, stratify=labels
    )
    
    print(f"Training samples: {len(train_passwords)}")
    print(f"Testing samples: {len(test_passwords)}")
    print()
    
    # Prepare labels
    print("Preparing one-hot encoded labels...")
    train_labels_encoded = prepare_labels(train_labels, predictor.strength_classes)
    test_labels_encoded = prepare_labels(test_labels, predictor.strength_classes)
    
    # Train model
    print("Starting model training...")
    print(f"Epochs: {epochs}")
    print(f"Batch size: {batch_size}")
    print()
    
    history = predictor.train(
        train_passwords,
        train_labels_encoded,
        epochs=epochs,
        batch_size=batch_size
    )
    
    # Evaluate on test set
    print()
    print("Evaluating model on test set...")
    test_encoded = np.array([predictor._encode_password(pwd)[0] for pwd in test_passwords])
    test_loss, test_accuracy, _ = predictor.model.evaluate(test_encoded, test_labels_encoded, verbose=0)
    
    print(f"Test Loss: {test_loss:.4f}")
    print(f"Test Accuracy: {test_accuracy:.4f}")
    print()
    
    # Save model metadata
    print("Saving model metadata to database...")
    model_path = predictor.model_path
    
    MLModelMetadata.objects.update_or_create(
        model_type='password_strength',
        defaults={
            'version': '1.0',
            'file_path': model_path,
            'accuracy': test_accuracy,
            'training_samples': num_samples,
            'hyperparameters': {
                'epochs': epochs,
                'batch_size': batch_size,
                'max_length': predictor.max_length,
                'vocab_size': predictor.vocab_size
            },
            'is_active': True,
            'notes': f'LSTM model trained on {num_samples} synthetic passwords'
        }
    )
    
    print("✓ Model training completed successfully!")
    print(f"✓ Model saved to: {model_path}")
    print()
    
    # Test predictions
    print("Testing predictions on sample passwords...")
    test_samples = [
        "password",
        "Password123",
        "P@ssw0rd!2024",
        "Tr0ub4dor&3",
        "correcthorsebatterystaple",
        "xK9#mL2$pR5@vN8!"
    ]
    
    for pwd in test_samples:
        result = predictor.predict(pwd)
        print(f"  '{pwd}' → {result['strength']} (confidence: {result['confidence']:.2f})")
    
    print()
    print("=" * 80)
    print("TRAINING COMPLETE!")
    print("=" * 80)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Train Password Strength LSTM Model')
    parser.add_argument('--samples', type=int, default=10000, help='Number of training samples')
    parser.add_argument('--epochs', type=int, default=50, help='Number of training epochs')
    parser.add_argument('--batch-size', type=int, default=32, help='Training batch size')
    
    args = parser.parse_args()
    
    try:
        train_model(
            num_samples=args.samples,
            epochs=args.epochs,
            batch_size=args.batch_size
        )
    except KeyboardInterrupt:
        print("\n\nTraining interrupted by user.")
    except Exception as e:
        print(f"\n\nError during training: {str(e)}")
        import traceback
        traceback.print_exc()

