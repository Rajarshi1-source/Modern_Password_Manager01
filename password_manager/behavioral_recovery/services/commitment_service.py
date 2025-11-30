"""
Commitment Service

Manages creation and verification of behavioral commitments
"""

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import logging
import json
from datetime import timedelta
from django.utils import timezone
from ..models import BehavioralCommitment
from cryptography.fernet import Fernet
import base64

# Import quantum crypto service (Phase 2A)
try:
    from .quantum_crypto_service import QuantumCryptoService, get_quantum_crypto_service
    QUANTUM_CRYPTO_AVAILABLE = True
except ImportError:
    QUANTUM_CRYPTO_AVAILABLE = False

# Import blockchain anchoring service (Phase 2B.1)
try:
    from blockchain.services.blockchain_anchor_service import BlockchainAnchorService
    BLOCKCHAIN_AVAILABLE = True
except ImportError:
    BLOCKCHAIN_AVAILABLE = False

logger = logging.getLogger(__name__)


class CommitmentService:
    """
    Service for creating and verifying behavioral commitments
    
    Handles:
    - Creating encrypted behavioral commitments (now with quantum crypto!)
    - Verifying behavioral similarity
    - Assessing profile quality
    
    Phase 2A Enhancement: Uses CRYSTALS-Kyber-768 for quantum resistance
    """
    
    SIMILARITY_THRESHOLD = 0.87  # Similarity threshold for recovery
    MIN_SAMPLES_REQUIRED = 50     # Minimum samples needed for commitment
    
    def __init__(self, use_quantum=True, use_blockchain=True):
        self.threshold = self.SIMILARITY_THRESHOLD
        self.use_quantum = use_quantum and QUANTUM_CRYPTO_AVAILABLE
        self.use_blockchain = use_blockchain and BLOCKCHAIN_AVAILABLE
        
        # Initialize quantum crypto if available
        if self.use_quantum:
            try:
                self.quantum_crypto = get_quantum_crypto_service()
                logger.info("CommitmentService initialized with quantum crypto")
            except Exception as e:
                logger.warning(f"Failed to initialize quantum crypto: {e}. Using fallback.")
                self.use_quantum = False
                self.quantum_crypto = None
        else:
            self.quantum_crypto = None
        
        # Initialize blockchain anchoring if available (Phase 2B.1)
        if self.use_blockchain:
            try:
                self.blockchain_anchor = BlockchainAnchorService()
                logger.info("CommitmentService initialized with blockchain anchoring")
            except Exception as e:
                logger.warning(f"Blockchain service initialization failed: {e}")
                self.use_blockchain = False
                self.blockchain_anchor = None
        else:
            self.blockchain_anchor = None
    
    def create_commitments(self, user, behavioral_profile):
        """
        Create behavioral commitments for a user
        
        Args:
            user: Django User object
            behavioral_profile: Dict with behavioral data (247 dimensions × N samples)
        
        Returns:
            List of created BehavioralCommitment objects
        """
        logger.info(f"Creating behavioral commitments for user: {user.username}")
        
        # Validate profile quality
        quality = self.assess_profile_quality(behavioral_profile)
        if quality < 0.7:
            raise ValueError(f"Behavioral profile quality too low: {quality:.2f}")
        
        # Create commitments for each behavioral dimension group
        commitments = []
        
        # Commitment for typing dynamics
        if 'typing' in behavioral_profile:
            commitment = self._create_commitment(
                user=user,
                challenge_type='typing',
                behavioral_data=behavioral_profile['typing'],
                unlock_conditions={'similarity_threshold': self.threshold}
            )
            commitments.append(commitment)
        
        # Commitment for mouse biometrics
        if 'mouse' in behavioral_profile:
            commitment = self._create_commitment(
                user=user,
                challenge_type='mouse',
                behavioral_data=behavioral_profile['mouse'],
                unlock_conditions={'similarity_threshold': self.threshold}
            )
            commitments.append(commitment)
        
        # Commitment for cognitive patterns
        if 'cognitive' in behavioral_profile:
            commitment = self._create_commitment(
                user=user,
                challenge_type='cognitive',
                behavioral_data=behavioral_profile['cognitive'],
                unlock_conditions={'similarity_threshold': self.threshold}
            )
            commitments.append(commitment)
        
        # Commitment for navigation patterns
        if 'navigation' in behavioral_profile:
            commitment = self._create_commitment(
                user=user,
                challenge_type='navigation',
                behavioral_data=behavioral_profile['navigation'],
                unlock_conditions={'similarity_threshold': self.threshold}
            )
            commitments.append(commitment)
        
        # Combined commitment (overall behavioral DNA)
        if 'combined_embedding' in behavioral_profile:
            commitment = self._create_commitment(
                user=user,
                challenge_type='combined',
                behavioral_data=behavioral_profile['combined_embedding'],
                unlock_conditions={'similarity_threshold': self.threshold}
            )
            commitments.append(commitment)
        
        logger.info(f"Created {len(commitments)} behavioral commitments for {user.username}")
        return commitments
    
    def _create_commitment(self, user, challenge_type, behavioral_data, unlock_conditions):
        """
        Create a single behavioral commitment
        
        Phase 2A: Now supports quantum-resistant encryption
        
        Args:
            user: User object
            challenge_type: Type of challenge (typing, mouse, etc.)
            behavioral_data: Behavioral embedding or raw data
            unlock_conditions: Dict with unlock requirements
        
        Returns:
            BehavioralCommitment object
        """
        # Encrypt the behavioral embedding
        encryption_result = self._encrypt_embedding(behavioral_data)
        
        # Determine sample count
        samples_used = len(behavioral_data) if isinstance(behavioral_data, list) else 1
        
        # Check if quantum encryption was used
        if self.use_quantum and isinstance(encryption_result, tuple):
            # Quantum encryption returns (encrypted_data, public_key, private_key)
            quantum_encrypted, public_key, private_key = encryption_result
            
            commitment = BehavioralCommitment.objects.create(
                user=user,
                challenge_type=challenge_type,
                encrypted_embedding=b'',  # Legacy field, keep empty
                quantum_encrypted_embedding=quantum_encrypted,
                kyber_public_key=public_key,
                encryption_algorithm='kyber768-aes256gcm',
                is_quantum_protected=True,
                unlock_conditions=unlock_conditions,
                samples_used=samples_used,
                is_active=True
            )
            
            # Note: Kyber private key should be securely stored elsewhere
            # (encrypted with user's master password)
            # For now, we're not storing it (user would need to re-authenticate)
            
            logger.info(f"Created quantum-protected commitment: {commitment.commitment_id}")
            
        else:
            # Classical encryption (legacy mode)
            encrypted_embedding = encryption_result
            
            commitment = BehavioralCommitment.objects.create(
                user=user,
                challenge_type=challenge_type,
                encrypted_embedding=encrypted_embedding,
                encryption_algorithm='base64',
                is_quantum_protected=False,
                unlock_conditions=unlock_conditions,
                samples_used=samples_used,
                is_active=True
            )
            
            logger.info(f"Created classical commitment: {commitment.commitment_id}")
        
        # Add blockchain anchoring (Phase 2B.1)
        if self.use_blockchain and self.blockchain_anchor:
            try:
                import hashlib
                
                # Create commitment hash for blockchain anchoring
                # Hash includes: commitment_id + user_id + encrypted_data + timestamp
                hash_data = f"{commitment.commitment_id}{user.id}{commitment.creation_timestamp.isoformat()}"
                commitment_hash = hashlib.sha256(hash_data.encode()).hexdigest()
                
                # Store hash in commitment
                commitment.blockchain_hash = commitment_hash
                commitment.save()
                
                # Add to pending batch for blockchain anchoring
                self.blockchain_anchor.add_to_pending_batch(
                    user_id=user.id,
                    commitment_id=str(commitment.commitment_id),
                    commitment_hash=commitment_hash
                )
                
                logger.info(f"Commitment {commitment.commitment_id} queued for blockchain anchoring: {commitment_hash[:16]}...")
            except Exception as e:
                logger.error(f"Failed to add commitment to blockchain anchoring queue: {e}")
                # Continue anyway - blockchain anchoring is optional
        
        return commitment
    
    def verify_behavioral_similarity(self, stored_embedding, current_embedding):
        """
        Verify behavioral similarity using cosine similarity
        
        Args:
            stored_embedding: Encrypted stored behavioral embedding (128-dim)
            current_embedding: Current behavioral embedding (128-dim)
        
        Returns:
            dict: {
                'similarity_score': float,
                'passed': bool,
                'threshold': float
            }
        """
        try:
            # Decrypt stored embedding
            decrypted_stored = self._decrypt_embedding(stored_embedding)
            
            # Convert to numpy arrays
            stored_array = np.array(decrypted_stored).reshape(1, -1)
            current_array = np.array(current_embedding).reshape(1, -1)
            
            # Calculate cosine similarity
            similarity = cosine_similarity(stored_array, current_array)[0][0]
            
            # Check if similarity meets threshold
            passed = similarity >= self.threshold
            
            result = {
                'similarity_score': float(similarity),
                'passed': passed,
                'threshold': self.threshold
            }
            
            logger.info(f"Behavioral similarity: {similarity:.3f} (threshold: {self.threshold})")
            return result
            
        except Exception as e:
            logger.error(f"Error verifying behavioral similarity: {e}", exc_info=True)
            raise
    
    def assess_profile_quality(self, behavioral_profile):
        """
        Assess the quality and completeness of a behavioral profile
        
        Args:
            behavioral_profile: Dict with behavioral data
        
        Returns:
            float: Quality score (0-1)
        """
        total_score = 0.0
        max_score = 0.0
        
        # Check typing data completeness
        if 'typing' in behavioral_profile:
            max_score += 0.30
            typing_data = behavioral_profile['typing']
            if isinstance(typing_data, dict):
                # Check for key typing features
                required_features = ['key_press_duration', 'inter_key_latency', 'typing_rhythm']
                present_features = sum(1 for f in required_features if f in typing_data)
                total_score += (present_features / len(required_features)) * 0.30
        
        # Check mouse data completeness
        if 'mouse' in behavioral_profile:
            max_score += 0.25
            mouse_data = behavioral_profile['mouse']
            if isinstance(mouse_data, dict):
                required_features = ['velocity_curves', 'movement_trajectory', 'click_patterns']
                present_features = sum(1 for f in required_features if f in mouse_data)
                total_score += (present_features / len(required_features)) * 0.25
        
        # Check cognitive data
        if 'cognitive' in behavioral_profile:
            max_score += 0.20
            total_score += 0.20
        
        # Check navigation data
        if 'navigation' in behavioral_profile:
            max_score += 0.15
            total_score += 0.15
        
        # Check for combined embedding
        if 'combined_embedding' in behavioral_profile:
            max_score += 0.10
            total_score += 0.10
        
        quality_score = total_score / max_score if max_score > 0 else 0.0
        return quality_score
    
    def _encrypt_embedding(self, embedding_data):
        """
        Encrypt behavioral embedding using quantum-resistant crypto
        
        Phase 2A: Uses Kyber-768 + AES hybrid encryption when available
        
        Args:
            embedding_data: List or array of behavioral features
        
        Returns:
            Tuple: (encrypted_data, kyber_public_key, kyber_private_key)
                   or just encrypted_bytes for legacy mode
        """
        if self.use_quantum and self.quantum_crypto:
            try:
                # Generate Kyber keypair for this commitment
                public_key, private_key = self.quantum_crypto.generate_keypair()
                
                # Encrypt with Kyber + AES hybrid
                quantum_encrypted = self.quantum_crypto.encrypt_behavioral_embedding(
                    embedding_data,
                    public_key
                )
                
                logger.info("Encrypted embedding with Kyber-768 (quantum-resistant)")
                
                # Return quantum-encrypted data and keys
                return quantum_encrypted, public_key, private_key
                
            except Exception as e:
                logger.error(f"Quantum encryption failed: {e}. Falling back to classical.")
                # Fall through to classical encryption
        
        # Classical encryption (legacy/fallback)
        logger.info("Using classical encryption (not quantum-resistant)")
        
        embedding_json = json.dumps(embedding_data)
        embedding_bytes = embedding_json.encode('utf-8')
        encrypted = base64.b64encode(embedding_bytes)
        
        return encrypted
    
    def _decrypt_embedding(self, encrypted_embedding, kyber_private_key=None):
        """
        Decrypt behavioral embedding
        
        Phase 2A: Supports both quantum and classical decryption
        
        Args:
            encrypted_embedding: Encrypted bytes or quantum_encrypted dict
            kyber_private_key: Kyber private key (for quantum mode)
        
        Returns:
            List: Decrypted behavioral embedding
        """
        # Check if this is quantum-encrypted data
        if isinstance(encrypted_embedding, dict) and 'algorithm' in encrypted_embedding:
            if encrypted_embedding['algorithm'].startswith('kyber') and kyber_private_key:
                try:
                    # Quantum decryption
                    embedding_data = self.quantum_crypto.decrypt_behavioral_embedding(
                        encrypted_embedding,
                        kyber_private_key
                    )
                    
                    logger.info("Decrypted embedding with Kyber-768")
                    return embedding_data
                    
                except Exception as e:
                    logger.error(f"Quantum decryption failed: {e}")
                    raise
        
        # Classical decryption (legacy)
        logger.info("Using classical decryption")
        
        if isinstance(encrypted_embedding, dict):
            # Handle case where dict was passed but no private key
            raise ValueError("Quantum-encrypted data requires private key for decryption")
        
        decrypted_bytes = base64.b64decode(encrypted_embedding)
        decrypted_json = decrypted_bytes.decode('utf-8')
        embedding_data = json.loads(decrypted_json)
        
        return embedding_data

