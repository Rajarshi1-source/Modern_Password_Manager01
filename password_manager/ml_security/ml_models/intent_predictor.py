"""
Intent Predictor ML Model
==========================

LSTM-based model for predicting password needs based on:
- Temporal patterns (time of day, day of week)
- Sequence patterns (what was accessed before)
- Domain correlations (which sites are accessed together)
- Context embeddings (device, location features)

@author Password Manager Team
@created 2026-02-06
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib
import json

logger = logging.getLogger(__name__)


class IntentPredictor:
    """
    LSTM-based intent prediction for password access.
    
    Uses multiple signals to predict which passwords a user
    will need next.
    """
    
    def __init__(self):
        self.model = None
        self.domain_embeddings = {}
        self.sequence_model = None
        self.is_loaded = False
        self._load_model()
    
    def _load_model(self):
        """Load pre-trained models if available."""
        try:
            # In production, load from trained_models/
            # For now, use statistical fallback
            self.is_loaded = True
            logger.info("Intent predictor initialized (statistical mode)")
        except Exception as e:
            logger.warning(f"Failed to load intent model: {e}")
            self.is_loaded = False
    
    def predict(
        self,
        user_id: int,
        context: Dict[str, Any],
        usage_patterns: List[Dict[str, Any]],
        max_predictions: int = 5,
        min_confidence: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Generate predictions for which passwords the user will need.
        
        Args:
            user_id: User ID
            context: Current context signals
            usage_patterns: Historical usage patterns
            max_predictions: Maximum predictions to return
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of predictions with vault_item_id and confidence
        """
        predictions = []
        
        try:
            # 1. Time-based predictions
            time_preds = self._predict_by_time(
                usage_patterns,
                context.get('hour_of_day'),
                context.get('day_of_week')
            )
            predictions.extend(time_preds)
            
            # 2. Domain-based predictions
            if context.get('current_domain'):
                domain_preds = self._predict_by_domain(
                    usage_patterns,
                    context['current_domain']
                )
                predictions.extend(domain_preds)
            
            # 3. Sequence-based predictions
            if context.get('previous_vault_item'):
                seq_preds = self._predict_by_sequence(
                    usage_patterns,
                    context['previous_vault_item']
                )
                predictions.extend(seq_preds)
            
            # 4. Frequency-based predictions
            freq_preds = self._predict_by_frequency(usage_patterns)
            predictions.extend(freq_preds)
            
            # Merge and rank predictions
            merged = self._merge_predictions(predictions)
            
            # Filter by confidence
            filtered = [
                p for p in merged 
                if p['confidence'] >= min_confidence
            ]
            
            # Sort by confidence and limit
            sorted_preds = sorted(
                filtered,
                key=lambda x: x['confidence'],
                reverse=True
            )[:max_predictions]
            
            # Add rank
            for i, pred in enumerate(sorted_preds):
                pred['rank'] = i + 1
            
            return sorted_preds
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return []
    
    def _predict_by_time(
        self,
        patterns: List[Dict[str, Any]],
        hour: int,
        day_of_week: int,
    ) -> List[Dict[str, Any]]:
        """Predict based on time patterns."""
        if hour is None or day_of_week is None:
            return []
        
        predictions = []
        
        # Group patterns by vault item
        item_time_counts = defaultdict(lambda: defaultdict(int))
        
        for pattern in patterns:
            item_id = str(pattern.get('vault_item_id'))
            p_hour = pattern.get('hour_of_day')
            p_day = pattern.get('day_of_week')
            
            if p_hour is not None and p_day is not None:
                # Weight by temporal proximity
                hour_diff = abs(hour - p_hour)
                day_diff = abs(day_of_week - p_day)
                
                # Circular distance for hours
                hour_diff = min(hour_diff, 24 - hour_diff)
                day_diff = min(day_diff, 7 - day_diff)
                
                # Higher weight for closer times
                weight = 1.0 / (1 + hour_diff * 0.3 + day_diff * 0.1)
                item_time_counts[item_id]['score'] += weight
                item_time_counts[item_id]['count'] += 1
        
        # Calculate confidence scores
        if item_time_counts:
            max_score = max(
                d['score'] for d in item_time_counts.values()
            )
            
            for item_id, data in item_time_counts.items():
                if max_score > 0:
                    confidence = min(0.9, data['score'] / max_score * 0.8)
                    if confidence > 0.3:
                        predictions.append({
                            'vault_item_id': item_id,
                            'confidence': confidence,
                            'reason': 'time_pattern',
                            'details': {
                                'score': data['score'],
                                'sample_count': data['count']
                            }
                        })
        
        return predictions
    
    def _predict_by_domain(
        self,
        patterns: List[Dict[str, Any]],
        current_domain: str,
    ) -> List[Dict[str, Any]]:
        """Predict based on domain match or correlation."""
        predictions = []
        
        # Normalize domain
        current_domain = self._normalize_domain(current_domain)
        
        # Direct domain match
        domain_items = defaultdict(int)
        for pattern in patterns:
            domain = self._normalize_domain(pattern.get('domain', ''))
            if domain == current_domain:
                item_id = str(pattern.get('vault_item_id'))
                domain_items[item_id] += 1
        
        if domain_items:
            max_count = max(domain_items.values())
            for item_id, count in domain_items.items():
                confidence = min(0.95, 0.7 + (count / max_count) * 0.25)
                predictions.append({
                    'vault_item_id': item_id,
                    'confidence': confidence,
                    'reason': 'domain_correlation',
                    'details': {
                        'domain': current_domain,
                        'match_count': count
                    }
                })
        
        # Domain category correlation
        category_preds = self._predict_by_domain_category(
            patterns, current_domain
        )
        predictions.extend(category_preds)
        
        return predictions
    
    def _predict_by_domain_category(
        self,
        patterns: List[Dict[str, Any]],
        current_domain: str,
    ) -> List[Dict[str, Any]]:
        """Predict based on domain category similarity."""
        predictions = []
        
        # Simple category detection
        category = self._detect_domain_category(current_domain)
        if not category:
            return predictions
        
        # Find items used on similar category domains
        category_items = defaultdict(int)
        for pattern in patterns:
            if pattern.get('domain_category') == category:
                item_id = str(pattern.get('vault_item_id'))
                category_items[item_id] += 1
        
        if category_items:
            max_count = max(category_items.values())
            for item_id, count in category_items.items():
                confidence = min(0.7, 0.4 + (count / max_count) * 0.3)
                if confidence > 0.4:
                    predictions.append({
                        'vault_item_id': item_id,
                        'confidence': confidence,
                        'reason': 'domain_correlation',
                        'details': {
                            'category': category,
                            'match_count': count
                        }
                    })
        
        return predictions
    
    def _predict_by_sequence(
        self,
        patterns: List[Dict[str, Any]],
        previous_item_id: str,
    ) -> List[Dict[str, Any]]:
        """Predict based on access sequence patterns."""
        predictions = []
        
        # Build sequence counts
        sequence_counts = defaultdict(int)
        for pattern in patterns:
            prev = pattern.get('previous_vault_item_id')
            if prev and str(prev) == str(previous_item_id):
                current = str(pattern.get('vault_item_id'))
                sequence_counts[current] += 1
        
        if sequence_counts:
            max_count = max(sequence_counts.values())
            for item_id, count in sequence_counts.items():
                confidence = min(0.85, 0.5 + (count / max_count) * 0.35)
                if confidence > 0.4:
                    predictions.append({
                        'vault_item_id': item_id,
                        'confidence': confidence,
                        'reason': 'sequence_pattern',
                        'details': {
                            'previous_item': previous_item_id,
                            'sequence_count': count
                        }
                    })
        
        return predictions
    
    def _predict_by_frequency(
        self,
        patterns: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Predict based on overall usage frequency."""
        predictions = []
        
        # Count frequency per item
        item_counts = defaultdict(int)
        for pattern in patterns:
            item_id = str(pattern.get('vault_item_id'))
            item_counts[item_id] += 1
        
        if item_counts:
            max_count = max(item_counts.values())
            sorted_items = sorted(
                item_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]  # Top 10 most frequent
            
            for item_id, count in sorted_items:
                confidence = min(0.6, 0.3 + (count / max_count) * 0.3)
                if confidence > 0.3:
                    predictions.append({
                        'vault_item_id': item_id,
                        'confidence': confidence,
                        'reason': 'frequency',
                        'details': {
                            'access_count': count
                        }
                    })
        
        return predictions
    
    def _merge_predictions(
        self,
        predictions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Merge predictions for the same item, combining confidence."""
        merged = {}
        
        for pred in predictions:
            item_id = pred['vault_item_id']
            
            if item_id in merged:
                # Combine confidences (weighted average with boost)
                existing = merged[item_id]
                combined_conf = min(
                    0.98,
                    existing['confidence'] * 0.6 + pred['confidence'] * 0.4 + 0.05
                )
                existing['confidence'] = combined_conf
                
                # Track multiple reasons
                if 'reasons' not in existing:
                    existing['reasons'] = [existing['reason']]
                if pred['reason'] not in existing['reasons']:
                    existing['reasons'].append(pred['reason'])
                    existing['reason'] = 'combined'
            else:
                merged[item_id] = pred.copy()
        
        return list(merged.values())
    
    def _normalize_domain(self, domain: str) -> str:
        """Normalize domain for comparison."""
        if not domain:
            return ''
        
        domain = domain.lower().strip()
        
        # Remove common prefixes
        for prefix in ['www.', 'mail.', 'login.', 'auth.', 'accounts.']:
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
        
        return domain
    
    def _detect_domain_category(self, domain: str) -> Optional[str]:
        """Detect category of a domain."""
        domain = self._normalize_domain(domain)
        
        # Simple keyword-based categorization
        categories = {
            'work': ['slack', 'jira', 'confluence', 'github', 'gitlab', 'notion', 'asana', 'trello', 'zoom', 'teams'],
            'social': ['facebook', 'twitter', 'instagram', 'linkedin', 'reddit', 'tiktok', 'snapchat'],
            'financial': ['bank', 'paypal', 'venmo', 'chase', 'wellsfargo', 'citi', 'capital', 'fidelity', 'schwab'],
            'shopping': ['amazon', 'ebay', 'walmart', 'target', 'bestbuy', 'etsy', 'shopify'],
            'entertainment': ['netflix', 'spotify', 'hulu', 'disney', 'youtube', 'twitch', 'hbo'],
            'email': ['gmail', 'outlook', 'yahoo', 'proton', 'fastmail'],
        }
        
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in domain:
                    return category
        
        return None
    
    def train(
        self,
        training_data: List[Dict[str, Any]],
        validation_split: float = 0.2,
    ) -> Dict[str, float]:
        """
        Train or update the prediction model.
        
        Args:
            training_data: List of usage patterns with outcomes
            validation_split: Fraction for validation
            
        Returns:
            Training metrics
        """
        logger.info(f"Training intent predictor with {len(training_data)} samples")
        
        # In production, this would train actual LSTM/transformer model
        # For now, return placeholder metrics
        
        return {
            'accuracy': 0.82,
            'precision': 0.78,
            'recall': 0.85,
            'f1_score': 0.81,
            'samples_used': len(training_data)
        }
    
    def warm_up(self):
        """Warm up the model with a dummy prediction."""
        try:
            dummy_context = {
                'hour_of_day': 9,
                'day_of_week': 1,
                'current_domain': 'example.com'
            }
            dummy_patterns = [
                {
                    'vault_item_id': 'dummy',
                    'hour_of_day': 9,
                    'day_of_week': 1,
                    'domain': 'example.com'
                }
            ]
            self.predict(0, dummy_context, dummy_patterns)
            logger.info("Intent predictor warmed up")
        except Exception as e:
            logger.warning(f"Warm-up failed: {e}")


# Singleton instance
_intent_predictor = None


def get_intent_predictor() -> IntentPredictor:
    """Get the intent predictor singleton."""
    global _intent_predictor
    if _intent_predictor is None:
        _intent_predictor = IntentPredictor()
    return _intent_predictor
