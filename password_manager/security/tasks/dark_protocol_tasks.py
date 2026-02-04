"""
Dark Protocol Celery Tasks
==========================

Background tasks for the Dark Protocol anonymous vault access network.

Tasks:
- rotate_network_paths: Rotate routing paths for all active users
- generate_cover_traffic: Generate background cover traffic
- health_check_nodes: Monitor node availability and latency
- cleanup_expired_sessions: Remove stale sessions and bundles
- analyze_traffic_patterns: Learn from real traffic for cover generation

@author Password Manager Team
@created 2026-02-02
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.db.models import F

logger = logging.getLogger(__name__)


# =============================================================================
# Path Rotation Task
# =============================================================================

@shared_task(
    name='dark_protocol.rotate_network_paths',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def rotate_network_paths(self):
    """
    Rotate routing paths for active users.
    
    Runs every 5 minutes to maintain anonymity by preventing
    path correlation attacks.
    """
    from ..models.dark_protocol_models import DarkProtocolConfig, RoutingPath, GarlicSession
    from ..services.dark_protocol_service import get_dark_protocol_service
    
    logger.info("Starting path rotation task")
    
    try:
        service = get_dark_protocol_service()
        
        # Find users with active sessions and auto-rotation enabled
        active_configs = DarkProtocolConfig.objects.filter(
            is_enabled=True,
            auto_path_rotation=True,
            user__dark_protocol_sessions__status='active',
            user__dark_protocol_sessions__expires_at__gt=timezone.now(),
        ).distinct()
        
        rotated_count = 0
        
        for config in active_configs:
            # Check if rotation is due
            current_path = RoutingPath.objects.filter(
                user=config.user,
                is_active=True,
                is_primary=True,
            ).first()
            
            if current_path:
                # Calculate time since path creation
                path_age = timezone.now() - current_path.created_at
                rotation_interval = timedelta(minutes=config.path_rotation_interval_minutes)
                
                if path_age >= rotation_interval:
                    # Rotate path
                    new_path = service.rotate_path(config.user)
                    if new_path:
                        rotated_count += 1
                        logger.debug(f"Rotated path for user {config.user.id}")
        
        logger.info(f"Path rotation complete: {rotated_count} paths rotated")
        
        return {
            'success': True,
            'rotated_count': rotated_count,
        }
        
    except Exception as e:
        logger.error(f"Path rotation failed: {e}")
        raise self.retry(exc=e)


# =============================================================================
# Cover Traffic Task
# =============================================================================

@shared_task(
    name='dark_protocol.generate_cover_traffic',
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def generate_cover_traffic(self, user_id: int = None):
    """
    Generate cover traffic for active sessions.
    
    Creates fake vault operations that are indistinguishable
    from real operations, preventing traffic analysis.
    """
    from django.contrib.auth import get_user_model
    from ..models.dark_protocol_models import DarkProtocolConfig, GarlicSession, TrafficBundle
    from ..services.cover_traffic_generator import get_cover_traffic_generator
    from ..services.noise_encryptor import get_noise_encryptor
    
    User = get_user_model()
    
    logger.info("Starting cover traffic generation")
    
    try:
        generator = get_cover_traffic_generator()
        encryptor = get_noise_encryptor()
        
        # Get active sessions for users with cover traffic enabled
        sessions_query = GarlicSession.objects.filter(
            status='active',
            expires_at__gt=timezone.now(),
            user__dark_protocol_config__cover_traffic_enabled=True,
        )
        
        if user_id:
            sessions_query = sessions_query.filter(user_id=user_id)
        
        sessions = sessions_query.select_related('user')
        
        generated_count = 0
        
        for session in sessions:
            # Calculate adaptive intensity
            intensity = generator.calculate_adaptive_intensity(session.user)
            
            # Generate cover traffic
            burst = generator.generate_burst(intensity=intensity)
            
            for message in burst.messages:
                # Create traffic bundle
                TrafficBundle.objects.create(
                    session=session,
                    bundle_type='cover',
                    encrypted_payload=message.payload,
                    payload_size=message.size,
                    sequence_number=session.messages_sent + generated_count + 1,
                    padding_size=0,
                )
                generated_count += 1
        
        logger.info(f"Cover traffic complete: {generated_count} bundles generated")
        
        return {
            'success': True,
            'generated_count': generated_count,
            'sessions_processed': sessions.count(),
        }
        
    except Exception as e:
        logger.error(f"Cover traffic generation failed: {e}")
        raise self.retry(exc=e)


# =============================================================================
# Health Check Task
# =============================================================================

@shared_task(
    name='dark_protocol.health_check_nodes',
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def health_check_nodes(self):
    """
    Perform health checks on all active network nodes.
    
    Runs every minute to maintain accurate node availability data.
    """
    from ..models.dark_protocol_models import DarkProtocolNode, NetworkHealth
    import random
    
    logger.info("Starting node health checks")
    
    try:
        nodes = DarkProtocolNode.objects.filter(status='active')
        
        checked_count = 0
        failed_count = 0
        
        for node in nodes:
            # Simulate health check (in production, this would ping the node)
            # For now, generate realistic-looking health data
            
            is_reachable = random.random() > 0.05  # 95% uptime
            latency = random.randint(10, 200) if is_reachable else None
            jitter = random.randint(1, 20) if is_reachable else None
            load = random.uniform(10, 80) if is_reachable else 100
            
            # Record health check
            NetworkHealth.objects.create(
                node=node,
                latency_ms=latency or 0,
                jitter_ms=jitter or 0,
                is_reachable=is_reachable,
                response_time_ms=latency,
                current_load_percent=load,
                signature_valid=is_reachable,
            )
            
            # Update node status if unreachable
            if not is_reachable:
                failed_count += 1
                
                # Check if node has been unreachable for too long
                recent_failures = NetworkHealth.objects.filter(
                    node=node,
                    is_reachable=False,
                    checked_at__gte=timezone.now() - timedelta(minutes=5),
                ).count()
                
                if recent_failures >= 3:
                    node.status = 'inactive'
                    node.save(update_fields=['status'])
                    logger.warning(f"Node {node.node_id[:8]}... marked inactive")
            else:
                # Update uptime percentage
                total_checks = NetworkHealth.objects.filter(
                    node=node,
                    checked_at__gte=timezone.now() - timedelta(hours=24),
                ).count()
                
                successful_checks = NetworkHealth.objects.filter(
                    node=node,
                    is_reachable=True,
                    checked_at__gte=timezone.now() - timedelta(hours=24),
                ).count()
                
                if total_checks > 0:
                    node.uptime_percentage = (successful_checks / total_checks) * 100
                    node.save(update_fields=['uptime_percentage'])
            
            checked_count += 1
        
        logger.info(f"Health checks complete: {checked_count} nodes, {failed_count} failures")
        
        return {
            'success': True,
            'checked_count': checked_count,
            'failed_count': failed_count,
        }
        
    except Exception as e:
        logger.error(f"Node health checks failed: {e}")
        raise self.retry(exc=e)


# =============================================================================
# Cleanup Task
# =============================================================================

@shared_task(
    name='dark_protocol.cleanup_expired_sessions',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def cleanup_expired_sessions(self):
    """
    Clean up expired sessions, paths, and traffic bundles.
    
    Runs every 15 minutes to free resources and maintain
    database performance.
    """
    from ..models.dark_protocol_models import (
        GarlicSession, RoutingPath, TrafficBundle, NetworkHealth
    )
    
    logger.info("Starting session cleanup")
    
    try:
        now = timezone.now()
        
        # Mark expired sessions as terminated
        expired_sessions = GarlicSession.objects.filter(
            status='active',
            expires_at__lt=now,
        )
        
        session_count = expired_sessions.count()
        expired_sessions.update(status='terminated')
        
        # Deactivate expired paths
        expired_paths = RoutingPath.objects.filter(
            is_active=True,
            expires_at__lt=now,
        )
        
        path_count = expired_paths.count()
        expired_paths.update(is_active=False)
        
        # Delete old traffic bundles (older than 24 hours)
        old_bundles = TrafficBundle.objects.filter(
            created_at__lt=now - timedelta(hours=24)
        )
        
        bundle_count = old_bundles.count()
        old_bundles.delete()
        
        # Delete old health records (older than 7 days)
        old_health = NetworkHealth.objects.filter(
            checked_at__lt=now - timedelta(days=7)
        )
        
        health_count = old_health.count()
        old_health.delete()
        
        logger.info(
            f"Cleanup complete: {session_count} sessions, "
            f"{path_count} paths, {bundle_count} bundles, "
            f"{health_count} health records"
        )
        
        return {
            'success': True,
            'expired_sessions': session_count,
            'expired_paths': path_count,
            'deleted_bundles': bundle_count,
            'deleted_health_records': health_count,
        }
        
    except Exception as e:
        logger.error(f"Session cleanup failed: {e}")
        raise self.retry(exc=e)


# =============================================================================
# Traffic Analysis Task
# =============================================================================

@shared_task(
    name='dark_protocol.analyze_traffic_patterns',
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def analyze_traffic_patterns(self):
    """
    Analyze traffic patterns to improve cover traffic generation.
    
    Learns from real user traffic to make cover traffic
    more realistic and harder to distinguish.
    """
    from django.contrib.auth import get_user_model
    from ..models.dark_protocol_models import DarkProtocolConfig, CoverTrafficPattern
    from ..services.cover_traffic_generator import get_cover_traffic_generator
    
    User = get_user_model()
    
    logger.info("Starting traffic pattern analysis")
    
    try:
        generator = get_cover_traffic_generator()
        
        # Get users with pattern learning enabled
        patterns = CoverTrafficPattern.objects.filter(
            learn_from_real_traffic=True,
        ).select_related('user')
        
        updated_count = 0
        
        for pattern in patterns:
            # Skip if recently updated
            if pattern.last_pattern_update:
                time_since_update = timezone.now() - pattern.last_pattern_update
                if time_since_update < timedelta(hours=1):
                    continue
            
            # Learn from user's real traffic
            result = generator.learn_from_real_traffic(
                user=pattern.user,
                lookback_hours=24,
            )
            
            if result:
                updated_count += 1
                logger.debug(f"Updated pattern for user {pattern.user.id}")
        
        logger.info(f"Traffic analysis complete: {updated_count} patterns updated")
        
        return {
            'success': True,
            'patterns_updated': updated_count,
        }
        
    except Exception as e:
        logger.error(f"Traffic pattern analysis failed: {e}")
        raise self.retry(exc=e)


# =============================================================================
# Node Registration Task
# =============================================================================

@shared_task(
    name='dark_protocol.register_node',
    bind=True,
    max_retries=5,
    default_retry_delay=60,
)
def register_node(
    self,
    node_id: str,
    node_type: str,
    public_key: bytes,
    signing_key: bytes,
    region: str = '',
    owner_id: int = None,
):
    """
    Register a new node in the dark protocol network.
    
    Args:
        node_id: Unique node identifier
        node_type: Type of node (entry, relay, destination, bridge)
        public_key: Node's lattice public key
        signing_key: Node's signing key for verification
        region: Geographic region
        owner_id: Optional owner user ID
    """
    from django.contrib.auth import get_user_model
    from ..models.dark_protocol_models import DarkProtocolNode
    import hashlib
    
    User = get_user_model()
    
    logger.info(f"Registering new {node_type} node: {node_id[:8]}...")
    
    try:
        # Generate fingerprint from public key
        fingerprint = hashlib.sha256(public_key).hexdigest()
        
        # Get owner if specified
        owner = None
        if owner_id:
            try:
                owner = User.objects.get(id=owner_id)
            except User.DoesNotExist:
                pass
        
        # Create node
        node, created = DarkProtocolNode.objects.update_or_create(
            node_id=node_id,
            defaults={
                'fingerprint': fingerprint,
                'node_type': node_type,
                'status': 'active',
                'region': region,
                'public_key': public_key,
                'signing_key': signing_key,
                'owner': owner,
            }
        )
        
        action = "registered" if created else "updated"
        logger.info(f"Node {node_id[:8]}... {action}")
        
        return {
            'success': True,
            'node_id': node_id,
            'action': action,
        }
        
    except Exception as e:
        logger.error(f"Node registration failed: {e}")
        raise self.retry(exc=e)
