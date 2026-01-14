"""
Adversarial AI Password Defense - Database Models
==================================================

Models for tracking adversarial simulations, attack vectors,
defense recommendations, and anonymized breach patterns.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json


class AdversarialBattle(models.Model):
    """
    Records each adversarial simulation (attack vs defense match).
    Stores the outcome and metrics for analysis and learning.
    """
    
    OUTCOME_CHOICES = [
        ('defender_wins', 'Defender Wins'),
        ('attacker_wins', 'Attacker Wins'),
        ('draw', 'Draw'),
        ('ongoing', 'Ongoing'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='adversarial_battles'
    )
    
    # Password analysis (never store actual password)
    password_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 hash of password for deduplication"
    )
    password_entropy = models.FloatField(
        help_text="Calculated entropy of the password"
    )
    password_length = models.IntegerField()
    
    # Battle metrics
    attack_score = models.FloatField(
        help_text="Attacker AI's success probability (0-1)"
    )
    defense_score = models.FloatField(
        help_text="Defender AI's protection score (0-1)"
    )
    estimated_crack_time_seconds = models.BigIntegerField(
        help_text="Estimated time to crack in seconds"
    )
    
    # Outcome
    outcome = models.CharField(
        max_length=20,
        choices=OUTCOME_CHOICES,
        default='ongoing'
    )
    
    # Attack vectors attempted
    attack_vectors_used = models.JSONField(
        default=list,
        help_text="List of attack vector IDs that were simulated"
    )
    
    # Defense strategies applied
    defense_strategies = models.JSONField(
        default=list,
        help_text="List of defense strategies that were effective"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['outcome']),
        ]
    
    def __str__(self):
        return f"Battle {self.id} - {self.user.username} - {self.outcome}"


class AttackVector(models.Model):
    """
    Catalog of attack techniques used by the Attacker AI.
    These represent known password cracking methods.
    """
    
    CATEGORY_CHOICES = [
        ('dictionary', 'Dictionary Attack'),
        ('brute_force', 'Brute Force'),
        ('rule_based', 'Rule-Based Mutation'),
        ('pattern', 'Pattern Recognition'),
        ('markov', 'Markov Chain'),
        ('hybrid', 'Hybrid Attack'),
        ('social', 'Social Engineering'),
        ('rainbow', 'Rainbow Table'),
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.TextField()
    
    # Attack parameters
    technique_details = models.JSONField(
        default=dict,
        help_text="Technical details of the attack method"
    )
    
    # Effectiveness metrics
    base_success_rate = models.FloatField(
        default=0.1,
        help_text="Base probability of success (0-1)"
    )
    severity = models.CharField(
        max_length=10,
        choices=SEVERITY_CHOICES,
        default='medium'
    )
    
    # Conditions when this attack is more likely to succeed
    vulnerable_patterns = models.JSONField(
        default=list,
        help_text="Password patterns vulnerable to this attack"
    )
    
    # Counter-measures
    recommended_defenses = models.JSONField(
        default=list,
        help_text="Defenses that mitigate this attack"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.category})"


class DefenseRecommendation(models.Model):
    """
    Personalized defense recommendations generated for users
    based on their password patterns and adversarial analysis.
    """
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('viewed', 'Viewed'),
        ('applied', 'Applied'),
        ('dismissed', 'Dismissed'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='defense_recommendations'
    )
    
    battle = models.ForeignKey(
        AdversarialBattle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recommendations'
    )
    
    # Recommendation content
    title = models.CharField(max_length=200)
    description = models.TextField()
    action_items = models.JSONField(
        default=list,
        help_text="Specific actions user should take"
    )
    
    # Context
    attack_vectors_addressed = models.ManyToManyField(
        AttackVector,
        blank=True,
        related_name='recommendations'
    )
    
    # Priority and status
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium'
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Impact estimate
    estimated_strength_improvement = models.FloatField(
        default=0.0,
        help_text="Estimated improvement in defense score if applied"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    viewed_at = models.DateTimeField(null=True, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-priority', '-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['priority', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"


class AggregatedBreachPattern(models.Model):
    """
    Anonymized, aggregated breach patterns for learning.
    NO PII is stored - only statistical patterns.
    
    This enables the system to learn from attacks without
    compromising user privacy.
    """
    
    PATTERN_TYPE_CHOICES = [
        ('length_distribution', 'Password Length Distribution'),
        ('char_class_combo', 'Character Class Combination'),
        ('common_prefix', 'Common Prefix Pattern'),
        ('common_suffix', 'Common Suffix Pattern'),
        ('keyboard_pattern', 'Keyboard Walk Pattern'),
        ('date_pattern', 'Date-Based Pattern'),
        ('leet_speak', 'Leet Speak Substitution'),
        ('dictionary_base', 'Dictionary Word Base'),
    ]
    
    pattern_type = models.CharField(max_length=30, choices=PATTERN_TYPE_CHOICES)
    pattern_signature = models.CharField(
        max_length=100,
        help_text="Anonymized pattern identifier"
    )
    
    # Aggregated statistics (no PII)
    occurrence_count = models.IntegerField(default=0)
    success_rate_against = models.FloatField(
        default=0.0,
        help_text="How often attacks succeed against this pattern"
    )
    
    # Pattern details (anonymized)
    pattern_features = models.JSONField(
        default=dict,
        help_text="Statistical features of the pattern"
    )
    
    # Associated attack vectors
    effective_attacks = models.ManyToManyField(
        AttackVector,
        blank=True,
        related_name='effective_against_patterns'
    )
    
    # Time tracking
    first_observed = models.DateTimeField(auto_now_add=True)
    last_observed = models.DateTimeField(auto_now=True)
    
    # Trend data
    is_trending = models.BooleanField(default=False)
    trend_velocity = models.FloatField(
        default=0.0,
        help_text="Rate of increase in observations"
    )
    
    class Meta:
        unique_together = ['pattern_type', 'pattern_signature']
        indexes = [
            models.Index(fields=['pattern_type', 'is_trending']),
            models.Index(fields=['occurrence_count']),
        ]
    
    def __str__(self):
        return f"{self.pattern_type}: {self.pattern_signature[:20]}..."


class UserDefenseProfile(models.Model):
    """
    Tracks a user's overall defense posture and history.
    Used to personalize recommendations and track improvement.
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='defense_profile'
    )
    
    # Overall scores
    overall_defense_score = models.FloatField(
        default=0.5,
        help_text="Current overall defense posture (0-1)"
    )
    historical_average_score = models.FloatField(
        default=0.5,
        help_text="Average defense score over time"
    )
    
    # Battle statistics
    total_battles = models.IntegerField(default=0)
    battles_won = models.IntegerField(default=0)
    battles_lost = models.IntegerField(default=0)
    
    # Vulnerability profile (anonymized patterns)
    common_vulnerabilities = models.JSONField(
        default=list,
        help_text="Common vulnerability patterns for this user"
    )
    
    # Strength profile
    strong_practices = models.JSONField(
        default=list,
        help_text="Security practices user does well"
    )
    
    # Learning data
    recommendations_applied = models.IntegerField(default=0)
    improvement_rate = models.FloatField(
        default=0.0,
        help_text="Rate of defense score improvement over time"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_battle_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name_plural = "User Defense Profiles"
    
    def __str__(self):
        return f"Defense Profile: {self.user.username} (Score: {self.overall_defense_score:.2f})"
    
    def update_from_battle(self, battle: AdversarialBattle):
        """Update profile based on a completed battle."""
        self.total_battles += 1
        self.last_battle_at = timezone.now()
        
        if battle.outcome == 'defender_wins':
            self.battles_won += 1
        elif battle.outcome == 'attacker_wins':
            self.battles_lost += 1
        
        # Update rolling average
        alpha = 0.1  # Smoothing factor
        self.overall_defense_score = (
            alpha * battle.defense_score +
            (1 - alpha) * self.overall_defense_score
        )
        
        self.save()
