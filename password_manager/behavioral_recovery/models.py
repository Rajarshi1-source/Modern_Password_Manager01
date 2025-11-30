"""
Behavioral Recovery Database Models

Models for storing behavioral commitments, recovery attempts, and challenges
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
import json


class BehavioralCommitment(models.Model):
    """
    Stores encrypted behavioral embeddings (commitments) for future recovery
    
    Each commitment represents a cryptographic commitment to the user's
    behavioral DNA at a specific point in time.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='behavioral_commitments')
    commitment_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    
    # Encrypted 128-dimensional behavioral embedding
    encrypted_embedding = models.BinaryField(
        help_text="Encrypted 128-dim behavioral DNA vector"
    )
    
    creation_timestamp = models.DateTimeField(auto_now_add=True)
    
    # Unlock conditions for this commitment
    unlock_conditions = models.JSONField(
        default=dict,
        help_text="Similarity threshold, temporal requirements, etc."
    )
    
    # Type of behavioral challenge associated with this commitment
    CHALLENGE_TYPES = [
        ('typing', 'Typing Dynamics'),
        ('mouse', 'Mouse Biometrics'),
        ('cognitive', 'Cognitive Patterns'),
        ('navigation', 'UI Navigation'),
        ('semantic', 'Semantic Behaviors'),
        ('combined', 'Combined Multi-modal'),
    ]
    challenge_type = models.CharField(max_length=50, choices=CHALLENGE_TYPES)
    
    # Active status (can be revoked if compromised)
    is_active = models.BooleanField(default=True)
    
    # Metadata
    samples_used = models.IntegerField(
        default=0,
        help_text="Number of behavioral samples used to create this commitment"
    )
    
    last_verified = models.DateTimeField(null=True, blank=True)
    
    # Post-Quantum Encryption Fields (Phase 2A)
    kyber_public_key = models.BinaryField(
        null=True,
        blank=True,
        help_text="Kyber-768 public key for this commitment (1184 bytes)"
    )
    
    kyber_ciphertext = models.BinaryField(
        null=True,
        blank=True,
        help_text="Kyber-encapsulated shared secret (1088 bytes)"
    )
    
    quantum_encrypted_embedding = models.JSONField(
        null=True,
        blank=True,
        help_text="Hybrid Kyber+AES encrypted embedding (complete encrypted data structure)"
    )
    
    encryption_algorithm = models.CharField(
        max_length=50,
        default='base64',
        help_text="Encryption algorithm: base64 (legacy), kyber768-aes256gcm (quantum)"
    )
    
    is_quantum_protected = models.BooleanField(
        default=False,
        help_text="Whether this commitment uses post-quantum encryption"
    )
    
    # Migration Support
    legacy_encrypted_embedding = models.BinaryField(
        null=True,
        blank=True,
        help_text="Original encryption format (preserved during migration)"
    )
    
    migrated_to_quantum = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when migrated to quantum encryption"
    )
    
    # Blockchain Anchoring (Phase 2B.1)
    blockchain_hash = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="SHA-256 hash for blockchain anchoring (hex string without 0x prefix)"
    )
    
    blockchain_anchored = models.BooleanField(
        default=False,
        help_text="Whether this commitment has been anchored to blockchain"
    )
    
    blockchain_anchored_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when anchored to blockchain"
    )
    
    class Meta:
        ordering = ['-creation_timestamp']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['commitment_id']),
        ]
    
    def __str__(self):
        return f"Behavioral Commitment {self.commitment_id} for {self.user.username}"


class BehavioralRecoveryAttempt(models.Model):
    """
    Tracks an ongoing password recovery attempt using behavioral verification
    
    Recovery timeline: 3-5 days with daily challenges
    """
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='recovery_attempts',
        null=True,
        blank=True,
        help_text="User may be null initially if email lookup hasn't completed"
    )
    
    attempt_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    
    # Recovery timeline
    started_at = models.DateTimeField(auto_now_add=True)
    expected_completion_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Current progress
    STAGES = [
        ('initiated', 'Recovery Initiated'),
        ('typing_challenge', 'Typing Dynamics Challenge'),
        ('mouse_challenge', 'Mouse Biometrics Challenge'),
        ('cognitive_challenge', 'Cognitive Challenge'),
        ('navigation_challenge', 'Navigation Challenge'),
        ('verification', 'Final Verification'),
        ('completed', 'Recovery Completed'),
        ('failed', 'Recovery Failed'),
    ]
    current_stage = models.CharField(max_length=50, choices=STAGES, default='initiated')
    
    # Progress tracking
    samples_collected = models.IntegerField(
        default=0,
        help_text="Total behavioral samples collected during recovery"
    )
    
    challenges_completed = models.IntegerField(default=0)
    challenges_total = models.IntegerField(default=20)  # 4-5 challenges per day × 5 days
    
    # Similarity scores per challenge type
    similarity_scores = models.JSONField(
        default=dict,
        help_text="Similarity scores for each challenge type"
    )
    
    # Overall similarity score (average)
    overall_similarity = models.FloatField(null=True, blank=True)
    
    # Recovery status
    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed Successfully'),
        ('failed', 'Failed - Low Similarity'),
        ('abandoned', 'Abandoned by User'),
        ('expired', 'Expired - Took Too Long'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    
    # Security
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_fingerprint = models.CharField(max_length=255, blank=True)
    
    # Contact info (for email-based recovery initiation)
    contact_email = models.EmailField(blank=True)
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['attempt_id']),
            models.Index(fields=['started_at']),
        ]
    
    def __str__(self):
        user_str = self.user.username if self.user else self.contact_email
        return f"Recovery Attempt {self.attempt_id} for {user_str} - {self.status}"
    
    def update_similarity_score(self, challenge_type, score):
        """Update similarity score for a specific challenge type"""
        if not isinstance(self.similarity_scores, dict):
            self.similarity_scores = {}
        
        self.similarity_scores[challenge_type] = score
        
        # Recalculate overall similarity
        scores = [s for s in self.similarity_scores.values() if s is not None]
        if scores:
            self.overall_similarity = sum(scores) / len(scores)
        
        self.save()


class BehavioralChallenge(models.Model):
    """
    Individual behavioral challenge within a recovery attempt
    
    Each challenge tests a specific dimension of behavioral DNA
    """
    recovery_attempt = models.ForeignKey(
        BehavioralRecoveryAttempt,
        on_delete=models.CASCADE,
        related_name='challenges'
    )
    
    challenge_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    
    # Challenge type (matches BehavioralCommitment)
    CHALLENGE_TYPES = [
        ('typing', 'Typing Dynamics'),
        ('mouse', 'Mouse Biometrics'),
        ('cognitive', 'Cognitive Patterns'),
        ('navigation', 'UI Navigation'),
        ('semantic', 'Semantic Behaviors'),
    ]
    challenge_type = models.CharField(max_length=50, choices=CHALLENGE_TYPES)
    
    # Challenge-specific data
    challenge_data = models.JSONField(
        help_text="Specific task/prompt for this challenge (e.g., sentence to type)"
    )
    
    # User's response
    user_response = models.JSONField(
        null=True,
        blank=True,
        help_text="Captured behavioral data from user's response"
    )
    
    # Evaluation results
    similarity_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Similarity to stored behavioral profile (0-1)"
    )
    
    passed = models.BooleanField(
        null=True,
        blank=True,
        help_text="Whether this challenge passed the similarity threshold"
    )
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    time_taken_seconds = models.IntegerField(null=True, blank=True)
    
    # Metadata
    attempt_number = models.IntegerField(
        default=1,
        help_text="Number of times this specific challenge was attempted"
    )
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['recovery_attempt', 'challenge_type']),
            models.Index(fields=['challenge_id']),
        ]
    
    def __str__(self):
        return f"{self.challenge_type} Challenge {self.challenge_id}"


class BehavioralProfileSnapshot(models.Model):
    """
    Periodic snapshots of user's behavioral profile
    
    Used for tracking behavioral evolution over time and
    detecting gradual changes vs sudden anomalies
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='behavioral_snapshots')
    snapshot_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    
    # Snapshot timing
    created_at = models.DateTimeField(auto_now_add=True)
    period_start = models.DateTimeField(
        help_text="Start of the time period this snapshot covers"
    )
    period_end = models.DateTimeField(
        help_text="End of the time period this snapshot covers"
    )
    
    # Encrypted behavioral embedding for this period
    encrypted_embedding = models.BinaryField(
        help_text="Encrypted 128-dim behavioral DNA for this time period"
    )
    
    # Statistics
    samples_count = models.IntegerField(
        default=0,
        help_text="Number of behavioral samples in this snapshot"
    )
    
    quality_score = models.FloatField(
        default=0.0,
        help_text="Quality/completeness of behavioral data (0-1)"
    )
    
    # Dimensional breakdown
    dimensional_coverage = models.JSONField(
        default=dict,
        help_text="How many dimensions were captured (out of 247)"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"Behavioral Snapshot {self.snapshot_id} for {self.user.username}"


# ==============================================================================
# Phase 2B.2: Evaluation Framework Models
# ==============================================================================

class RecoveryFeedback(models.Model):
    """
    User feedback after completing a recovery attempt
    
    Collects quantitative and qualitative data for evaluation framework (Phase 2B.2)
    """
    recovery_attempt = models.OneToOneField(
        BehavioralRecoveryAttempt,
        on_delete=models.CASCADE,
        related_name='feedback'
    )
    
    # Quantitative Metrics (1-10 scale)
    security_perception = models.IntegerField(
        null=True,
        blank=True,
        help_text="User's perceived security level (1=very insecure, 10=very secure)"
    )
    
    ease_of_use = models.IntegerField(
        null=True,
        blank=True,
        help_text="How easy was the recovery process? (1=very difficult, 10=very easy)"
    )
    
    trust_level = models.IntegerField(
        null=True,
        blank=True,
        help_text="Trust in the behavioral recovery system (1=no trust, 10=complete trust)"
    )
    
    time_perception = models.IntegerField(
        null=True,
        blank=True,
        help_text="Was the recovery time acceptable? (1=too long, 5=perfect)"
    )
    
    # Net Promoter Score (0-10)
    nps_rating = models.IntegerField(
        null=True,
        blank=True,
        help_text="How likely to recommend this system? (0=not at all, 10=extremely likely)"
    )
    
    # Qualitative Feedback
    feedback_text = models.TextField(
        blank=True,
        help_text="Open-ended feedback from user"
    )
    
    # Specific Feature Ratings
    challenge_difficulty = models.IntegerField(
        null=True,
        blank=True,
        help_text="Were the challenges appropriate? (1=too hard, 5=perfect, 10=too easy)"
    )
    
    would_use_again = models.BooleanField(
        null=True,
        blank=True,
        help_text="Would you use behavioral recovery again?"
    )
    
    # Metadata
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-submitted_at']
        verbose_name = "Recovery Feedback"
        verbose_name_plural = "Recovery Feedback"
    
    def __str__(self):
        return f"Feedback for {self.recovery_attempt.attempt_id}"
    
    @property
    def is_promoter(self):
        """NPS Promoter (9-10)"""
        return self.nps_rating is not None and self.nps_rating >= 9
    
    @property
    def is_detractor(self):
        """NPS Detractor (0-6)"""
        return self.nps_rating is not None and self.nps_rating <= 6
    
    @property
    def average_satisfaction(self):
        """Calculate average satisfaction across all metrics"""
        scores = [
            self.security_perception,
            self.ease_of_use,
            self.trust_level,
            self.time_perception,
            self.challenge_difficulty
        ]
        valid_scores = [s for s in scores if s is not None]
        return sum(valid_scores) / len(valid_scores) if valid_scores else None


class RecoveryPerformanceMetric(models.Model):
    """
    Technical performance metrics for the recovery system
    
    Tracks system performance, costs, and technical KPIs (Phase 2B.2)
    """
    # Metric Identification
    metric_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Type of metric (e.g., 'blockchain_tx', 'ml_inference', 'recovery_time')"
    )
    
    # Metric Value
    value = models.FloatField(
        help_text="Numeric value of the metric"
    )
    
    unit = models.CharField(
        max_length=20,
        help_text="Unit of measurement (e.g., 'ms', 'seconds', 'percentage', 'USD')"
    )
    
    # Context
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recovery_performance_metrics'
    )
    
    recovery_attempt = models.ForeignKey(
        BehavioralRecoveryAttempt,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='performance_metrics'
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        help_text="Additional context and details about this metric"
    )
    
    recorded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Metric Types
    METRIC_TYPES = [
        ('blockchain_tx_time', 'Blockchain Transaction Time'),
        ('blockchain_gas_cost', 'Blockchain Gas Cost'),
        ('ml_inference_time', 'ML Model Inference Time'),
        ('merkle_proof_generation', 'Merkle Proof Generation Time'),
        ('recovery_total_time', 'Total Recovery Time'),
        ('challenge_completion_time', 'Challenge Completion Time'),
        ('similarity_computation', 'Similarity Computation Time'),
        ('quantum_encryption_time', 'Quantum Encryption Time'),
        ('quantum_decryption_time', 'Quantum Decryption Time'),
        ('api_response_time', 'API Response Time'),
        ('database_query_time', 'Database Query Time'),
        ('celery_task_duration', 'Celery Task Duration'),
    ]
    
    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['metric_type', 'recorded_at']),
            models.Index(fields=['user', 'recorded_at']),
            models.Index(fields=['recovery_attempt']),
        ]
        verbose_name = "Performance Metric"
        verbose_name_plural = "Performance Metrics"
    
    def __str__(self):
        return f"{self.metric_type}: {self.value} {self.unit} at {self.recorded_at}"


class RecoveryAuditLog(models.Model):
    """Audit log for recovery events and security incidents"""
    recovery_attempt = models.ForeignKey(
        'BehavioralRecoveryAttempt',
        on_delete=models.CASCADE,
        related_name='audit_logs'
    )
    event_type = models.CharField(
        max_length=50,
        choices=[
            ('recovery_initiated', 'Recovery Initiated'),
            ('challenge_completed', 'Challenge Completed'),
            ('challenge_failed', 'Challenge Failed'),
            ('adversarial_detected', 'Adversarial Activity Detected'),
            ('replay_detected', 'Replay Attack Detected'),
            ('suspicious_activity', 'Suspicious Activity'),
            ('recovery_completed', 'Recovery Completed'),
            ('recovery_failed', 'Recovery Failed'),
        ],
        help_text="Type of event logged"
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional details about the event"
    )
    severity = models.CharField(
        max_length=20,
        choices=[
            ('info', 'Info'),
            ('warning', 'Warning'),
            ('critical', 'Critical'),
        ],
        default='info',
        help_text="Severity level of the event"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Recovery Audit Log'
        verbose_name_plural = 'Recovery Audit Logs'
        indexes = [
            models.Index(fields=['recovery_attempt', '-timestamp']),
            models.Index(fields=['event_type', '-timestamp']),
            models.Index(fields=['severity', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.recovery_attempt.attempt_id} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

