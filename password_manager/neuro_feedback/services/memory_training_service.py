"""
Memory Training Service
=======================

Implements password memory training using:
- Chunked password presentation
- Spaced repetition scheduling (SuperMemo SM-2 algorithm + brain optimization)
- Memory strength tracking with forgetting curve modeling
- Progress persistence

@author Password Manager Team
@created 2026-02-07
"""

import logging
import hashlib
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import timedelta
from django.utils import timezone
from django.db import transaction

from ..models import (
    PasswordTrainingProgram,
    MemoryStrengthScore,
    SpacedRepetitionSchedule,
    BrainwaveSession,
    NeuroFeedbackSettings,
)
from .brainwave_analyzer import BrainwaveMetrics, BrainState

logger = logging.getLogger(__name__)


@dataclass
class TrainingChunk:
    """A password chunk for training presentation."""
    index: int
    content: str  # Actual chunk content (encrypted in transit)
    display_content: str  # Masked or partial for UI
    strength: float
    is_mastered: bool
    next_review_at: Optional[str] = None


@dataclass
class TrainingSession:
    """Current training session state."""
    program_id: str
    current_chunk: int
    total_chunks: int
    chunk_content: str
    chunk_strength: float
    time_remaining_seconds: int
    brain_state_optimal: bool
    feedback_message: str


@dataclass
class RecallResult:
    """Result of a recall attempt."""
    success: bool
    time_ms: int
    strength_delta: float
    new_strength: float
    feedback: str


class MemoryTrainingService:
    """
    Orchestrates password memory training with neurofeedback.
    """
    
    # SuperMemo SM-2 constants
    MIN_EASINESS = 1.3
    MAX_EASINESS = 2.5
    INITIAL_INTERVAL = 1.0  # days
    
    # Memory strength thresholds
    MASTERY_THRESHOLD = 0.9
    WEAK_THRESHOLD = 0.3
    
    # Forgetting curve parameters (Ebbinghaus)
    STABILITY_BASE = 0.9
    
    def __init__(self, user):
        self.user = user
        self._settings = None
    
    @property
    def settings(self) -> NeuroFeedbackSettings:
        """Get or create user settings."""
        if self._settings is None:
            self._settings, _ = NeuroFeedbackSettings.objects.get_or_create(
                user=self.user
            )
        return self._settings
    
    # =========================================================================
    # Program Management
    # =========================================================================
    
    @transaction.atomic
    def create_training_program(
        self,
        vault_item,
        password: str
    ) -> PasswordTrainingProgram:
        """
        Create a new password training program.
        
        Args:
            vault_item: The vault item containing the password
            password: The actual password to memorize (not stored)
            
        Returns:
            Created PasswordTrainingProgram
        """
        chunk_size = self.settings.chunk_size
        chunks = self._chunk_password(password, chunk_size)
        
        program = PasswordTrainingProgram.objects.create(
            user=self.user,
            vault_item=vault_item,
            password_hash=hashlib.sha256(password.encode()).hexdigest(),
            password_length=len(password),
            chunk_count=len(chunks),
            status='not_started',
            next_review_at=timezone.now(),
        )
        
        # Create memory strength records for each chunk
        for i, chunk in enumerate(chunks):
            MemoryStrengthScore.objects.create(
                program=program,
                chunk_index=i,
                chunk_hash=hashlib.sha256(chunk.encode()).hexdigest(),
                strength_score=0.0,
            )
        
        logger.info(
            f"Created training program for {len(password)}-char password "
            f"({len(chunks)} chunks) for user {self.user.username}"
        )
        
        return program
    
    def get_active_programs(self) -> List[PasswordTrainingProgram]:
        """Get all active training programs for the user."""
        return list(PasswordTrainingProgram.objects.filter(
            user=self.user,
            status__in=['not_started', 'in_progress', 'paused']
        ).select_related('vault_item'))
    
    def get_program_progress(self, program: PasswordTrainingProgram) -> Dict[str, Any]:
        """Get detailed progress for a training program."""
        scores = program.memory_scores.all()
        
        mastered = sum(1 for s in scores if s.is_mastered)
        weak = sum(1 for s in scores if s.strength_score < self.WEAK_THRESHOLD)
        avg_strength = sum(s.strength_score for s in scores) / len(scores) if scores else 0
        
        return {
            'program_id': str(program.id),
            'vault_item_id': str(program.vault_item.id),
            'status': program.status,
            'total_chunks': program.chunk_count,
            'chunks_mastered': mastered,
            'chunks_weak': weak,
            'average_strength': round(avg_strength, 3),
            'total_sessions': program.total_sessions,
            'total_practice_time_minutes': program.total_practice_time // 60,
            'next_review_at': program.next_review_at.isoformat() if program.next_review_at else None,
            'completion_percentage': round((mastered / program.chunk_count) * 100, 1),
            'estimated_days_remaining': self._estimate_completion_days(program, avg_strength),
        }
    
    # =========================================================================
    # Training Session
    # =========================================================================
    
    def start_training_session(
        self,
        program: PasswordTrainingProgram,
        password: str,
        session: BrainwaveSession
    ) -> TrainingSession:
        """
        Start a training session for a program.
        
        Args:
            program: The training program
            password: The actual password (for chunk display)
            session: The active brainwave session
        """
        if program.status == 'not_started':
            program.status = 'in_progress'
            program.started_at = timezone.now()
            program.save()
        
        # Find the weakest chunk to practice
        scores = list(program.memory_scores.order_by('strength_score'))
        weakest = scores[0] if scores else None
        
        if not weakest:
            raise ValueError("No chunks found for program")
        
        # Get the actual chunk content
        chunks = self._chunk_password(password, self.settings.chunk_size)
        chunk_content = chunks[weakest.chunk_index] if weakest.chunk_index < len(chunks) else ""
        
        return TrainingSession(
            program_id=str(program.id),
            current_chunk=weakest.chunk_index,
            total_chunks=program.chunk_count,
            chunk_content=chunk_content,
            chunk_strength=weakest.strength_score,
            time_remaining_seconds=self.settings.session_duration_minutes * 60,
            brain_state_optimal=False,
            feedback_message="Focus your attention. We'll show the password chunk when your brain is ready.",
        )
    
    def get_next_chunk(
        self,
        program: PasswordTrainingProgram,
        password: str,
        brain_metrics: BrainwaveMetrics
    ) -> Tuple[TrainingChunk, str]:
        """
        Get the next chunk to practice based on memory strength and brain state.
        
        Returns:
            Tuple of (TrainingChunk, feedback_message)
        """
        chunks = self._chunk_password(password, self.settings.chunk_size)
        scores = {s.chunk_index: s for s in program.memory_scores.all()}
        
        # Check if brain is in optimal state
        optimal = brain_metrics.brain_state in [
            BrainState.MEMORY_READY,
            BrainState.FOCUSED,
            BrainState.ENCODING,
        ]
        
        if not optimal:
            feedback = self._get_brain_state_feedback(brain_metrics)
            # Return current chunk but with guidance
            current_idx = program.current_chunk
            score = scores.get(current_idx)
            
            return TrainingChunk(
                index=current_idx,
                content="",  # Don't show content until ready
                display_content="• • • • • • • •",
                strength=score.strength_score if score else 0,
                is_mastered=score.is_mastered if score else False,
            ), feedback
        
        # Find best chunk to practice using spaced repetition
        chunk_to_practice = self._select_chunk_for_practice(scores, chunks)
        score = scores.get(chunk_to_practice)
        
        program.current_chunk = chunk_to_practice
        program.save(update_fields=['current_chunk'])
        
        return TrainingChunk(
            index=chunk_to_practice,
            content=chunks[chunk_to_practice],
            display_content=self._format_chunk_display(chunks[chunk_to_practice]),
            strength=score.strength_score if score else 0,
            is_mastered=score.is_mastered if score else False,
        ), "Great focus! Memorize this chunk now."
    
    # =========================================================================
    # Recall Testing
    # =========================================================================
    
    def test_recall(
        self,
        program: PasswordTrainingProgram,
        chunk_index: int,
        user_input: str,
        password: str,
        response_time_ms: int,
        brain_metrics: Optional[BrainwaveMetrics] = None
    ) -> RecallResult:
        """
        Test user's recall of a password chunk.
        
        Args:
            program: The training program
            chunk_index: Which chunk was tested
            user_input: User's typed input
            password: The actual password
            response_time_ms: Time taken to respond
            brain_metrics: Optional brain state during recall
        """
        chunks = self._chunk_password(password, self.settings.chunk_size)
        correct_chunk = chunks[chunk_index] if chunk_index < len(chunks) else ""
        
        success = user_input == correct_chunk
        
        # Get or create memory score
        score, _ = MemoryStrengthScore.objects.get_or_create(
            program=program,
            chunk_index=chunk_index,
            defaults={'chunk_hash': hashlib.sha256(correct_chunk.encode()).hexdigest()}
        )
        
        # Calculate quality (0-5 for SM-2)
        quality = self._calculate_recall_quality(success, response_time_ms, brain_metrics)
        
        # Update memory strength using SM-2 algorithm with forgetting curve
        old_strength = score.strength_score
        new_strength = self._update_memory_strength(score, quality, brain_metrics)
        strength_delta = new_strength - old_strength
        
        # Update score record
        if success:
            score.successful_recalls += 1
        else:
            score.failed_recalls += 1
        
        score.last_practiced_at = timezone.now()
        
        if score.avg_recall_time_ms:
            score.avg_recall_time_ms = int(
                (score.avg_recall_time_ms + response_time_ms) / 2
            )
        else:
            score.avg_recall_time_ms = response_time_ms
        
        if score.is_mastered and not score.mastered_at:
            score.mastered_at = timezone.now()
        
        score.save()
        
        # Update program stats
        program.total_sessions += 1
        program.chunks_mastered = sum(1 for s in program.memory_scores.all() if s.is_mastered)
        program.save()
        
        # Generate feedback
        feedback = self._generate_recall_feedback(success, quality, strength_delta, brain_metrics)
        
        return RecallResult(
            success=success,
            time_ms=response_time_ms,
            strength_delta=strength_delta,
            new_strength=new_strength,
            feedback=feedback,
        )
    
    # =========================================================================
    # Spaced Repetition Scheduling
    # =========================================================================
    
    def schedule_next_review(
        self,
        program: PasswordTrainingProgram,
        performance_quality: float
    ) -> SpacedRepetitionSchedule:
        """
        Schedule the next review based on SM-2 algorithm.
        
        Args:
            program: The training program
            performance_quality: 0-5 rating of recent performance
        """
        # Update easiness factor
        ef = program.easiness_factor
        ef = ef + (0.1 - (5 - performance_quality) * (0.08 + (5 - performance_quality) * 0.02))
        ef = max(self.MIN_EASINESS, min(ef, self.MAX_EASINESS))
        
        # Calculate next interval
        if program.review_count == 0:
            interval = 1
        elif program.review_count == 1:
            interval = 6
        else:
            interval = program.current_interval_days * ef
        
        # Brain-optimized scheduling
        # Recommend morning reviews for better encoding
        next_review = timezone.now() + timedelta(days=interval)
        
        # Adjust to morning if possible
        optimal_hour = 9  # 9 AM
        if next_review.hour < optimal_hour:
            next_review = next_review.replace(hour=optimal_hour, minute=0)
        
        schedule = SpacedRepetitionSchedule.objects.create(
            program=program,
            scheduled_at=next_review,
            interval_days=interval,
            predicted_strength=self._predict_strength_at_time(program, next_review),
            optimal_difficulty=0.6,  # Target difficulty for optimal learning
            recommended_time_of_day="morning",
            brain_state_recommendations={
                "target_alpha": 0.3,
                "target_focus": 0.6,
                "pre_session_relaxation": True,
            },
        )
        
        # Update program
        program.easiness_factor = ef
        program.current_interval_days = interval
        program.review_count += 1
        program.next_review_at = next_review
        program.last_reviewed_at = timezone.now()
        program.save()
        
        return schedule
    
    def get_due_reviews(self) -> List[PasswordTrainingProgram]:
        """Get all programs due for review."""
        return list(PasswordTrainingProgram.objects.filter(
            user=self.user,
            status='in_progress',
            next_review_at__lte=timezone.now(),
        ))
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _chunk_password(self, password: str, chunk_size: int) -> List[str]:
        """Split password into chunks of specified size."""
        return [
            password[i:i + chunk_size]
            for i in range(0, len(password), chunk_size)
        ]
    
    def _select_chunk_for_practice(
        self,
        scores: Dict[int, MemoryStrengthScore],
        chunks: List[str]
    ) -> int:
        """Select optimal chunk for practice using weighted random selection."""
        if not scores:
            return 0
        
        # Prioritize weaker chunks
        weights = []
        indices = []
        
        for idx in range(len(chunks)):
            score = scores.get(idx)
            strength = score.strength_score if score else 0
            
            # Weight inversely proportional to strength
            weight = 1.0 - strength + 0.1  # Add small constant to include mastered chunks occasionally
            weights.append(weight)
            indices.append(idx)
        
        # Normalize weights
        total = sum(weights)
        weights = [w / total for w in weights]
        
        # Weighted random selection
        import random
        return random.choices(indices, weights=weights)[0]
    
    def _calculate_recall_quality(
        self,
        success: bool,
        response_time_ms: int,
        brain_metrics: Optional[BrainwaveMetrics]
    ) -> int:
        """
        Calculate recall quality (0-5) for SM-2 algorithm.
        
        0 - Complete blackout
        1 - Incorrect after long hesitation
        2 - Incorrect but close
        3 - Correct with difficulty
        4 - Correct after hesitation
        5 - Perfect recall
        """
        if not success:
            if response_time_ms > 10000:
                return 0  # Complete blackout
            elif response_time_ms > 5000:
                return 1
            else:
                return 2
        
        # Success - determine quality based on speed
        if response_time_ms < 2000:
            base_quality = 5  # Fast and correct
        elif response_time_ms < 4000:
            base_quality = 4
        else:
            base_quality = 3
        
        # Adjust based on brain state if available
        if brain_metrics and brain_metrics.brain_state == BrainState.RECALL:
            base_quality = min(5, base_quality + 1)
        
        return base_quality
    
    def _update_memory_strength(
        self,
        score: MemoryStrengthScore,
        quality: int,
        brain_metrics: Optional[BrainwaveMetrics]
    ) -> float:
        """
        Update memory strength using modified Ebbinghaus forgetting curve.
        """
        current = score.strength_score
        
        # Base update
        if quality >= 3:
            # Successful recall - increase strength
            boost = 0.1 + (quality - 3) * 0.05
            
            # Extra boost if in optimal brain state
            if brain_metrics and brain_metrics.memory_readiness > 0.6:
                boost *= 1.3
            
            new_strength = min(1.0, current + boost)
        else:
            # Failed recall - decrease strength
            penalty = 0.1 + (2 - quality) * 0.05
            new_strength = max(0.0, current - penalty)
        
        # Apply decay since last practice
        if score.last_practiced_at:
            hours_since = (timezone.now() - score.last_practiced_at).total_seconds() / 3600
            decay = math.exp(-hours_since / (score.decay_rate * 100))
            new_strength *= decay
        
        score.strength_score = new_strength
        
        if new_strength > score.peak_strength:
            score.peak_strength = new_strength
        
        return new_strength
    
    def _predict_strength_at_time(
        self,
        program: PasswordTrainingProgram,
        future_time
    ) -> float:
        """Predict average memory strength at a future time."""
        scores = program.memory_scores.all()
        if not scores:
            return 0
        
        hours_until = (future_time - timezone.now()).total_seconds() / 3600
        
        predicted_strengths = []
        for score in scores:
            decay = math.exp(-hours_until / (score.decay_rate * 100))
            predicted = score.strength_score * decay
            predicted_strengths.append(predicted)
        
        return sum(predicted_strengths) / len(predicted_strengths)
    
    def _estimate_completion_days(
        self,
        program: PasswordTrainingProgram,
        avg_strength: float
    ) -> int:
        """Estimate days to complete training."""
        if avg_strength >= self.MASTERY_THRESHOLD:
            return 0
        
        # Rough estimate based on current progress
        chunks_remaining = program.chunk_count - program.chunks_mastered
        days_per_chunk = 2  # Average days to master one chunk
        
        return chunks_remaining * days_per_chunk
    
    def _get_brain_state_feedback(self, metrics: BrainwaveMetrics) -> str:
        """Generate feedback message based on brain state."""
        state_messages = {
            BrainState.UNFOCUSED: "Try to focus your attention. Take a deep breath.",
            BrainState.RELAXED: "Good relaxation! Now gently focus your attention.",
            BrainState.DISTRACTED: "Your mind is wandering. Gently bring your focus back.",
            BrainState.FATIGUE: "You seem tired. Consider taking a short break.",
        }
        return state_messages.get(metrics.brain_state, "Preparing...")
    
    def _format_chunk_display(self, chunk: str) -> str:
        """Format chunk for visual display."""
        return ' '.join(chunk)  # Add spacing between characters
    
    def _generate_recall_feedback(
        self,
        success: bool,
        quality: int,
        strength_delta: float,
        brain_metrics: Optional[BrainwaveMetrics]
    ) -> str:
        """Generate encouraging feedback after recall attempt."""
        if success:
            if quality == 5:
                return "🎉 Perfect! Lightning-fast recall!"
            elif quality == 4:
                return "✅ Great job! Memory is strengthening."
            else:
                return "👍 Correct! Keep practicing for faster recall."
        else:
            if quality == 0:
                return "💭 No worries! Let's review this chunk again."
            elif quality == 1:
                return "🔄 Almost there! Focus and try again."
            else:
                return "📝 Close! Pay attention to the exact characters."
