"""
pgvector Service for Similarity Search

Provides efficient similarity search using PostgreSQL pgvector extension.

This is OPTIONAL - the system will work without it using traditional queries.
pgvector is only needed for:
- Large-scale semantic search (>10k breaches)
- Real-time similarity matching
- Advanced ML features

Installation:
    pip install pgvector
    
    # In PostgreSQL:
    CREATE EXTENSION IF NOT EXISTS vector;
"""

import logging
import numpy as np
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

# Check if pgvector is available
try:
    from pgvector.django import VectorField
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    logger.warning("pgvector not installed. Similarity search will use fallback methods.")


class PgVectorService:
    """Service for vector similarity operations"""
    
    def __init__(self):
        self.enabled = PGVECTOR_AVAILABLE
        if not self.enabled:
            logger.info("pgvector disabled - using fallback methods")
    
    def generate_embedding(self, text: str, model='bert') -> Optional[np.ndarray]:
        """
        Generate embedding vector for text
        
        Args:
            text: Text to embed
            model: Model to use ('bert' or 'sentence-transformers')
        
        Returns:
            768-dimensional embedding vector or None
        """
        if not self.enabled:
            return None
        
        try:
            if model == 'bert':
                from ml_dark_web.ml_services import get_breach_classifier
                classifier = get_breach_classifier()
                
                # Get BERT embeddings
                inputs = classifier.tokenizer(
                    text,
                    padding=True,
                    truncation=True,
                    max_length=512,
                    return_tensors='pt'
                )
                
                with classifier.torch.no_grad():
                    outputs = classifier.model(**inputs)
                    # Use [CLS] token embedding
                    embedding = outputs.last_hidden_state[:, 0, :].numpy()[0]
                
                return embedding
            
            else:
                logger.warning(f"Unsupported model: {model}")
                return None
        
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    
    def find_similar_breaches(
        self,
        query_embedding: np.ndarray,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Tuple[int, float]]:
        """
        Find similar breaches using vector similarity search
        
        Args:
            query_embedding: Query vector (768-dim)
            limit: Maximum number of results
            similarity_threshold: Minimum cosine similarity
        
        Returns:
            List of (breach_id, similarity_score) tuples
        """
        if not self.enabled:
            return []
        
        try:
            from ml_dark_web.models import MLBreachData
            from django.db import connection
            
            # Convert numpy array to string format for PostgreSQL
            vector_str = '[' + ','.join(map(str, query_embedding)) + ']'
            
            # Use raw SQL for pgvector similarity search
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, 1 - (content_embedding <=> %s::vector) AS similarity
                    FROM ml_breach_data
                    WHERE content_embedding IS NOT NULL
                      AND 1 - (content_embedding <=> %s::vector) > %s
                    ORDER BY content_embedding <=> %s::vector
                    LIMIT %s;
                    """,
                    [vector_str, vector_str, similarity_threshold, vector_str, limit]
                )
                
                results = cursor.fetchall()
            
            return [(row[0], row[1]) for row in results]
        
        except Exception as e:
            logger.error(f"Error in similarity search: {e}")
            return []
    
    def find_similar_credentials(
        self,
        credential_text: str,
        limit: int = 10
    ) -> List[Tuple[int, float]]:
        """
        Find credentials similar to the query
        
        Args:
            credential_text: Credential to search for
            limit: Maximum results
        
        Returns:
            List of (credential_id, similarity_score)
        """
        if not self.enabled:
            return []
        
        # Generate embedding for query
        embedding = self.generate_embedding(credential_text)
        if embedding is None:
            return []
        
        try:
            from ml_dark_web.models import UserCredentialMonitoring
            from django.db import connection
            
            vector_str = '[' + ','.join(map(str, embedding)) + ']'
            
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, 1 - (credential_embedding <=> %s::vector) AS similarity
                    FROM ml_user_credential_monitoring
                    WHERE credential_embedding IS NOT NULL
                      AND is_active = TRUE
                    ORDER BY credential_embedding <=> %s::vector
                    LIMIT %s;
                    """,
                    [vector_str, vector_str, limit]
                )
                
                results = cursor.fetchall()
            
            return [(row[0], row[1]) for row in results]
        
        except Exception as e:
            logger.error(f"Error finding similar credentials: {e}")
            return []
    
    def update_breach_embedding(self, breach_id: int, text: str) -> bool:
        """
        Update embedding for a breach
        
        Args:
            breach_id: ID of the breach
            text: Text content to embed
        
        Returns:
            True if successful
        """
        if not self.enabled:
            return False
        
        try:
            from ml_dark_web.models import MLBreachData
            
            # Generate embedding
            embedding = self.generate_embedding(text)
            if embedding is None:
                return False
            
            # Update database
            breach = MLBreachData.objects.get(id=breach_id)
            
            # Convert numpy array to list for JSON/vector storage
            embedding_list = embedding.tolist()
            
            # Use raw SQL to update vector column
            from django.db import connection
            vector_str = '[' + ','.join(map(str, embedding)) + ']'
            
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE ml_breach_data SET content_embedding = %s::vector WHERE id = %s;",
                    [vector_str, breach_id]
                )
            
            logger.info(f"Updated embedding for breach {breach_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error updating breach embedding: {e}")
            return False
    
    def batch_update_embeddings(self, batch_size: int = 100) -> int:
        """
        Update embeddings for all breaches without embeddings
        
        Args:
            batch_size: Number of breaches to process at once
        
        Returns:
            Number of embeddings updated
        """
        if not self.enabled:
            return 0
        
        try:
            from ml_dark_web.models import MLBreachData
            from django.db import connection
            
            # Find breaches without embeddings
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, description FROM ml_breach_data "
                    "WHERE content_embedding IS NULL LIMIT %s;",
                    [batch_size]
                )
                breaches = cursor.fetchall()
            
            updated = 0
            for breach_id, description in breaches:
                if self.update_breach_embedding(breach_id, description):
                    updated += 1
            
            logger.info(f"Updated {updated} breach embeddings")
            return updated
        
        except Exception as e:
            logger.error(f"Error in batch update: {e}")
            return 0


# Global instance
pgvector_service = PgVectorService()


# Celery task for batch updating embeddings
def update_all_embeddings_task():
    """Celery task to update all embeddings"""
    from celery import shared_task
    
    @shared_task
    def update_embeddings_batch():
        """Update embeddings in batches"""
        if not pgvector_service.enabled:
            logger.warning("pgvector not enabled")
            return {'success': False, 'message': 'pgvector not available'}
        
        total_updated = 0
        batch_size = 100
        
        while True:
            updated = pgvector_service.batch_update_embeddings(batch_size)
            total_updated += updated
            
            if updated < batch_size:
                # No more breaches to update
                break
        
        return {
            'success': True,
            'total_updated': total_updated
        }
    
    return update_embeddings_batch

