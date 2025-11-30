"""
Recovery Metrics Collector (Phase 2B.2)

Central service for calculating and reporting behavioral recovery metrics.
Provides comprehensive KPIs for evaluation framework and decision-making.
"""

from django.db.models import Count, Avg, Q, F
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
from typing import Dict, Optional
import logging

from ..models import (
    BehavioralRecoveryAttempt,
    BehavioralCommitment,
    RecoveryFeedback,
    RecoveryPerformanceMetric,
    RecoveryAuditLog
)
from blockchain.models import BlockchainAnchor, MerkleProof

User = get_user_model()
logger = logging.getLogger(__name__)


class RecoveryMetricsCollector:
    """
    Collects and calculates comprehensive metrics for behavioral recovery system.
    
    Usage:
        collector = RecoveryMetricsCollector()
        metrics = collector.get_dashboard_metrics()
    """
    
    def __init__(self, time_range_days: int = 30):
        """
        Initialize metrics collector
        
        Args:
            time_range_days: Number of days to analyze (default: 30)
        """
        self.time_range_days = time_range_days
        self.cutoff_date = timezone.now() - timedelta(days=time_range_days)
    
    def calculate_success_rate(self) -> float:
        """
        Calculate recovery success rate
        
        Returns:
            Success rate as percentage (0-100)
        """
        try:
            total = BehavioralRecoveryAttempt.objects.filter(
                started_at__gte=self.cutoff_date
            ).count()
            
            if total == 0:
                return 0.0
            
            successful = BehavioralRecoveryAttempt.objects.filter(
                started_at__gte=self.cutoff_date,
                status='completed'
            ).count()
            
            rate = (successful / total) * 100
            
            logger.info(f"Recovery success rate: {rate:.2f}% ({successful}/{total})")
            return round(rate, 2)
            
        except Exception as e:
            logger.error(f"Error calculating success rate: {e}")
            return 0.0
    
    def calculate_false_positive_rate(self) -> float:
        """
        CRITICAL METRIC: Track unauthorized recoveries
        
        This is the most important security metric. Any value > 0 is a critical failure.
        
        Returns:
            False positive rate as percentage (target: 0.0%)
        """
        try:
            total_recoveries = BehavioralRecoveryAttempt.objects.filter(
                started_at__gte=self.cutoff_date,
                status='completed'
            ).count()
            
            if total_recoveries == 0:
                return 0.0
            
            # Check for recoveries flagged as suspicious/unauthorized
            suspicious_recoveries = RecoveryAuditLog.objects.filter(
                timestamp__gte=self.cutoff_date,
                event_type__in=['adversarial_detected', 'replay_detected', 'suspicious_activity'],
                recovery_attempt__status='completed'  # Completed despite being suspicious
            ).values('recovery_attempt').distinct().count()
            
            rate = (suspicious_recoveries / total_recoveries) * 100
            
            if rate > 0:
                logger.critical(f"⚠️ FALSE POSITIVE DETECTED: {rate:.4f}% ({suspicious_recoveries}/{total_recoveries})")
            else:
                logger.info(f"✅ No false positives detected ({total_recoveries} recoveries)")
            
            return round(rate, 4)
            
        except Exception as e:
            logger.error(f"Error calculating false positive rate: {e}")
            return 0.0
    
    def calculate_avg_recovery_time(self) -> float:
        """
        Calculate average time to complete recovery (in hours)
        
        Returns:
            Average recovery time in hours
        """
        try:
            completed_attempts = BehavioralRecoveryAttempt.objects.filter(
                started_at__gte=self.cutoff_date,
                status='completed',
                completed_at__isnull=False
            )
            
            if not completed_attempts.exists():
                return 0.0
            
            total_seconds = 0
            count = 0
            
            for attempt in completed_attempts:
                duration = (attempt.completed_at - attempt.started_at).total_seconds()
                total_seconds += duration
                count += 1
            
            avg_seconds = total_seconds / count if count > 0 else 0
            avg_hours = avg_seconds / 3600
            
            logger.info(f"Average recovery time: {avg_hours:.2f} hours")
            return round(avg_hours, 2)
            
        except Exception as e:
            logger.error(f"Error calculating average recovery time: {e}")
            return 0.0
    
    def calculate_user_satisfaction(self) -> Optional[float]:
        """
        Calculate average user satisfaction score (1-10 scale)
        
        Returns:
            Average satisfaction score or None if no data
        """
        try:
            feedback = RecoveryFeedback.objects.filter(
                submitted_at__gte=self.cutoff_date
            )
            
            if not feedback.exists():
                return None
            
            # Calculate average across all satisfaction metrics
            avg_scores = []
            
            for metric in ['security_perception', 'ease_of_use', 'trust_level']:
                avg = feedback.aggregate(Avg(metric))[f'{metric}__avg']
                if avg is not None:
                    avg_scores.append(avg)
            
            if not avg_scores:
                return None
            
            overall_satisfaction = sum(avg_scores) / len(avg_scores)
            
            logger.info(f"User satisfaction: {overall_satisfaction:.2f}/10")
            return round(overall_satisfaction, 2)
            
        except Exception as e:
            logger.error(f"Error calculating user satisfaction: {e}")
            return None
    
    def calculate_nps_score(self) -> Optional[float]:
        """
        Calculate Net Promoter Score (NPS)
        
        NPS = (% Promoters - % Detractors)
        - Promoters: rating 9-10
        - Passives: rating 7-8 (not included in calculation)
        - Detractors: rating 0-6
        
        Returns:
            NPS score (-100 to 100) or None if insufficient data
        """
        try:
            feedback = RecoveryFeedback.objects.filter(
                submitted_at__gte=self.cutoff_date,
                nps_rating__isnull=False
            )
            
            total = feedback.count()
            
            if total == 0:
                return None
            
            promoters = feedback.filter(nps_rating__gte=9).count()
            detractors = feedback.filter(nps_rating__lte=6).count()
            
            nps = ((promoters - detractors) / total) * 100
            
            logger.info(f"NPS Score: {nps:.1f} (Promoters: {promoters}, Detractors: {detractors}, Total: {total})")
            return round(nps, 1)
            
        except Exception as e:
            logger.error(f"Error calculating NPS score: {e}")
            return None
    
    def calculate_model_accuracy(self) -> Optional[float]:
        """
        Calculate behavioral model accuracy based on challenge success rates
        
        Returns:
            Model accuracy as percentage or None if insufficient data
        """
        try:
            # Get attempts with completed challenges
            from ..models import BehavioralChallenge
            
            completed_challenges = BehavioralChallenge.objects.filter(
                created_at__gte=self.cutoff_date,
                status='completed'
            )
            
            total = completed_challenges.count()
            
            if total == 0:
                return None
            
            # Calculate average similarity scores for completed challenges
            avg_similarity = completed_challenges.aggregate(
                Avg('similarity_score')
            )['similarity_score__avg']
            
            if avg_similarity is None:
                return None
            
            # Convert similarity score to accuracy percentage
            accuracy = avg_similarity * 100
            
            logger.info(f"Model accuracy: {accuracy:.2f}%")
            return round(accuracy, 2)
            
        except Exception as e:
            logger.error(f"Error calculating model accuracy: {e}")
            return None
    
    def calculate_blockchain_verification_rate(self) -> float:
        """
        Calculate percentage of commitments successfully anchored to blockchain
        
        Returns:
            Blockchain verification rate as percentage (target: 100%)
        """
        try:
            total_commitments = BehavioralCommitment.objects.filter(
                creation_timestamp__gte=self.cutoff_date
            ).count()
            
            if total_commitments == 0:
                return 100.0  # No commitments to anchor
            
            anchored = BehavioralCommitment.objects.filter(
                creation_timestamp__gte=self.cutoff_date,
                blockchain_anchored=True
            ).count()
            
            rate = (anchored / total_commitments) * 100
            
            logger.info(f"Blockchain verification rate: {rate:.2f}% ({anchored}/{total_commitments})")
            return round(rate, 2)
            
        except Exception as e:
            logger.error(f"Error calculating blockchain verification rate: {e}")
            return 0.0
    
    def calculate_cost_metrics(self) -> Dict[str, float]:
        """
        Calculate cost per recovery and related financial metrics
        
        Returns:
            Dictionary with cost metrics
        """
        try:
            # Calculate blockchain costs
            anchors = BlockchainAnchor.objects.filter(
                timestamp__gte=self.cutoff_date
            )
            
            total_gas_cost_wei = 0
            for anchor in anchors:
                if anchor.gas_used and anchor.gas_price_wei:
                    total_gas_cost_wei += (anchor.gas_used * anchor.gas_price_wei)
            
            # Convert to ETH and USD (approximate)
            total_cost_eth = total_gas_cost_wei / 1e18
            eth_price_usd = 2000  # Approximate, should be fetched from API in production
            total_cost_usd = total_cost_eth * eth_price_usd
            
            # Calculate cost per recovery
            total_recoveries = BehavioralRecoveryAttempt.objects.filter(
                started_at__gte=self.cutoff_date,
                status='completed'
            ).count()
            
            cost_per_recovery = total_cost_usd / total_recoveries if total_recoveries > 0 else 0
            
            # Calculate cost per commitment
            total_commitments = BehavioralCommitment.objects.filter(
                creation_timestamp__gte=self.cutoff_date
            ).count()
            
            cost_per_commitment = total_cost_usd / total_commitments if total_commitments > 0 else 0
            
            metrics = {
                'total_cost_usd': round(total_cost_usd, 2),
                'total_cost_eth': round(total_cost_eth, 6),
                'cost_per_recovery': round(cost_per_recovery, 4),
                'cost_per_commitment': round(cost_per_commitment, 6),
                'blockchain_transactions': anchors.count()
            }
            
            logger.info(f"Cost metrics: ${cost_per_recovery:.4f} per recovery, {anchors.count()} blockchain txs")
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating cost metrics: {e}")
            return {
                'total_cost_usd': 0.0,
                'total_cost_eth': 0.0,
                'cost_per_recovery': 0.0,
                'cost_per_commitment': 0.0,
                'blockchain_transactions': 0
            }
    
    def calculate_performance_metrics(self) -> Dict[str, float]:
        """
        Calculate technical performance metrics (response times, etc.)
        
        Returns:
            Dictionary with performance metrics
        """
        try:
            metrics = {}
            
            # Calculate average times for different operations
            metric_types = [
                'blockchain_tx_time',
                'ml_inference_time',
                'api_response_time',
                'quantum_encryption_time',
                'merkle_proof_generation'
            ]
            
            for metric_type in metric_types:
                avg = RecoveryPerformanceMetric.objects.filter(
                    recorded_at__gte=self.cutoff_date,
                    metric_type=metric_type
                ).aggregate(Avg('value'))['value__avg']
                
                if avg is not None:
                    metrics[metric_type] = round(avg, 2)
                else:
                    metrics[metric_type] = None
            
            logger.info(f"Performance metrics calculated: {len([m for m in metrics.values() if m is not None])} metrics available")
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return {}
    
    def calculate_user_abandonment_rate(self) -> float:
        """
        Calculate percentage of recovery attempts that were abandoned
        
        Returns:
            Abandonment rate as percentage
        """
        try:
            total_attempts = BehavioralRecoveryAttempt.objects.filter(
                started_at__gte=self.cutoff_date
            ).count()
            
            if total_attempts == 0:
                return 0.0
            
            abandoned = BehavioralRecoveryAttempt.objects.filter(
                started_at__gte=self.cutoff_date,
                status='failed'
            ).count()
            
            rate = (abandoned / total_attempts) * 100
            
            logger.info(f"User abandonment rate: {rate:.2f}% ({abandoned}/{total_attempts})")
            return round(rate, 2)
            
        except Exception as e:
            logger.error(f"Error calculating abandonment rate: {e}")
            return 0.0
    
    def get_dashboard_metrics(self) -> Dict:
        """
        Get comprehensive dashboard metrics
        
        Returns:
            Dictionary with all metrics for dashboard display
        """
        logger.info(f"Collecting dashboard metrics for last {self.time_range_days} days...")
        
        try:
            metrics = {
                # Security Metrics (Critical)
                'false_positive_rate': self.calculate_false_positive_rate(),
                'blockchain_verification_rate': self.calculate_blockchain_verification_rate(),
                
                # User Experience Metrics
                'recovery_success_rate': self.calculate_success_rate(),
                'average_recovery_time': self.calculate_avg_recovery_time(),
                'user_satisfaction': self.calculate_user_satisfaction(),
                'user_abandonment_rate': self.calculate_user_abandonment_rate(),
                
                # Business Metrics
                'nps_score': self.calculate_nps_score(),
                'cost_metrics': self.calculate_cost_metrics(),
                
                # Technical Metrics
                'model_accuracy': self.calculate_model_accuracy(),
                'performance_metrics': self.calculate_performance_metrics(),
                
                # Metadata
                'time_range_days': self.time_range_days,
                'generated_at': timezone.now().isoformat(),
            }
            
            logger.info("✅ Dashboard metrics collected successfully")
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error collecting dashboard metrics: {e}")
            raise
    
    def get_trending_metrics(self, periods: int = 7) -> Dict:
        """
        Get trending data for metrics over multiple time periods
        
        Args:
            periods: Number of time periods to analyze
            
        Returns:
            Dictionary with trending data
        """
        trends = {
            'success_rate': [],
            'user_satisfaction': [],
            'nps_score': [],
            'dates': []
        }
        
        for i in range(periods):
            days_ago = i * self.time_range_days
            period_start = timezone.now() - timedelta(days=days_ago + self.time_range_days)
            period_end = timezone.now() - timedelta(days=days_ago)
            
            # Temporarily adjust cutoff for this period
            original_cutoff = self.cutoff_date
            self.cutoff_date = period_start
            
            trends['success_rate'].append(self.calculate_success_rate())
            trends['user_satisfaction'].append(self.calculate_user_satisfaction())
            trends['nps_score'].append(self.calculate_nps_score())
            trends['dates'].append(period_start.strftime('%Y-%m-%d'))
            
            # Restore original cutoff
            self.cutoff_date = original_cutoff
        
        return trends
    
    def track_performance_metric(
        self,
        metric_type: str,
        value: float,
        unit: str,
        user=None,
        recovery_attempt=None,
        metadata: Dict = None
    ):
        """
        Helper method to track a performance metric
        
        Args:
            metric_type: Type of metric (e.g., 'api_response_time')
            value: Numeric value
            unit: Unit of measurement (e.g., 'ms', 'seconds')
            user: Optional user reference
            recovery_attempt: Optional recovery attempt reference
            metadata: Optional additional data
        """
        try:
            RecoveryPerformanceMetric.objects.create(
                metric_type=metric_type,
                value=value,
                unit=unit,
                user=user,
                recovery_attempt=recovery_attempt,
                metadata=metadata or {}
            )
        except Exception as e:
            logger.error(f"Error tracking performance metric {metric_type}: {e}")

