from celery import shared_task
from django.contrib.auth.models import User
from django.core.cache import cache
from vault.models.vault_models import EncryptedVaultItem
from vault.models import BreachAlert
from ..services.breach_monitor import HIBPService
from ..services.crypto_service import CryptoService
from ..services.account_protection import account_protection_service
import json
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

@shared_task
def check_for_breaches(user_id, data_type='password', identifiers=None):
    """
    Check if user's data has been compromised in known data breaches
    
    Args:
        user_id (int): ID of the user to check
        data_type (str): Type of data to check (password, email, etc.)
        identifiers (list): List of specific identifiers to check (password IDs, emails, etc.)
        
    Returns:
        dict: Results of the breach check
    """
    try:
        user = User.objects.get(id=user_id)
        results = {
            'checked': 0,
            'breached': 0,
            'items': []
        }
        
        if data_type == 'password':
            # Get password items to check
            if identifiers:
                items = EncryptedVaultItem.objects.filter(
                    user=user, 
                    id__in=identifiers, 
                    item_type='password'
                )
            else:
                items = EncryptedVaultItem.objects.filter(
                    user=user, 
                    item_type='password'
                )
                
            # Check each password
            for item in items:
                results['checked'] += 1
                
                # This is a stub - in reality you would decrypt the item
                # securely to get access to the password
                password = item.get_decrypted_password(user)
                
                if password:
                    # Hash the password
                    hash_value = HIBPService.hash_password(password)
                    prefix = hash_value[:5]
                    suffix = hash_value[5:]
                    
                    # Check if password is breached
                    breach_results = HIBPService.check_password_prefix(prefix)
                    
                    if suffix in breach_results:
                        breach_count = breach_results[suffix]
                        
                        # Create breach alert
                        BreachAlert.objects.get_or_create(
                            user=user,
                            data_type='password',
                            identifier=item.id,
                            defaults={
                                'breach_name': 'Password Breach',
                                'breach_description': f'This password was found in {breach_count} data breaches',
                                'severity': 'high' if breach_count > 1000 else 'medium',
                                'detected_at': timezone.now()
                            }
                        )
                        
                        results['breached'] += 1
                        results['items'].append({
                            'id': item.id,
                            'name': item.name,
                            'count': breach_count
                        })
        
        elif data_type == 'email':
            # Check email breaches
            emails = []
            
            if identifiers:
                emails = identifiers
            else:
                # Get user's primary email
                emails.append(user.email)
                
                # Get emails from vault items
                email_items = EncryptedVaultItem.objects.filter(
                    user=user,
                    item_type='login'
                )
                
                for item in email_items:
                    # This would decrypt the item in a real implementation
                    email = item.get_decrypted_field(user, 'username')
                    if email and '@' in email:
                        emails.append(email)
            
            # Remove duplicates
            emails = list(set(emails))
            
            # Check each email
            for email in emails:
                results['checked'] += 1
                
                # Check breach service
                breaches = HIBPService.check_email(email)
                
                if breaches:
                    # Create breach alert for each breach
                    for breach in breaches:
                        BreachAlert.objects.get_or_create(
                            user=user,
                            data_type='email',
                            identifier=email,
                            breach_name=breach.get('Name', 'Unknown Breach'),
                            defaults={
                                'breach_description': breach.get('Description', 'Your email was found in a data breach'),
                                'breach_date': breach.get('BreachDate'),
                                'severity': 'high',
                                'detected_at': timezone.now()
                            }
                        )
                    
                    results['breached'] += 1
                    results['items'].append({
                        'email': email,
                        'breach_count': len(breaches)
                    })
        
        return results
    
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        raise Exception(f"User {user_id} not found")
    
    except Exception as e:
        logger.error(f"Error checking breaches: {str(e)}")
        raise Exception(f"Error checking breaches: {str(e)}")

@shared_task(bind=True)
def scan_user_vault(self, user_id):
    """
    Scan a user's vault for passwords that have been exposed in data breaches
    
    Args:
        user_id (int): ID of the user to scan
        
    Returns:
        dict: Results of the scan
    """
    try:
        user = User.objects.get(id=user_id)
        vault_items = EncryptedVaultItem.objects.filter(user=user, item_type='password')
        
        # Set up progress tracking
        total_items = vault_items.count()
        processed = 0
        breached = 0
        breached_items = []
        
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={'progress': 0, 'total': total_items}
        )
        
        # Process each password item
        for item in vault_items:
            processed += 1
            
            try:
                # In a real implementation, this would decrypt the password
                # For this example, we're assuming direct access to the plaintext
                # which would need to be handled securely in production
                
                # This is a stub - in reality you would decrypt the item
                # securely to get access to the password
                password = item.get_decrypted_password(user)
                
                if password:
                    # Hash the password
                    hash_value = HIBPService.hash_password(password)
                    prefix = hash_value[:5]
                    suffix = hash_value[5:]
                    
                    # Check if password is breached
                    result = HIBPService.check_password_prefix(prefix)
                    
                    if suffix in result:
                        breach_count = result[suffix]
                        
                        # Create breach alert
                        BreachAlert.objects.get_or_create(
                            user=user,
                            data_type='password',
                            identifier=item.id,
                            defaults={
                                'breach_name': 'Password Breach',
                                'breach_description': f'This password was found in {breach_count} data breaches',
                                'severity': 'high' if breach_count > 1000 else 'medium',
                                'detected_at': timezone.now()
                            }
                        )
                        
                        breached += 1
                        breached_items.append({
                            'id': item.id,
                            'count': breach_count
                        })
            
            except Exception as e:
                logger.error(f"Error processing item {item.id}: {str(e)}")
            
            # Update progress
            if processed % 5 == 0 or processed == total_items:
                self.update_state(
                    state='PROGRESS',
                    meta={'progress': (processed / total_items) * 100, 'total': total_items}
                )
        
        # Return the final result
        return {
            'total': total_items,
            'breached': breached,
            'items': breached_items
        }
    
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        raise Exception(f"User {user_id} not found")
    
    except Exception as e:
        logger.error(f"Error scanning vault: {str(e)}")
        raise Exception(f"Error scanning vault: {str(e)}")

# Scheduled task to run daily
@shared_task
def daily_breach_scan():
    """
    Daily scheduled task to scan all users' vaults
    """
    # Get all active users
    users = User.objects.filter(is_active=True)
    
    for user in users:
        # Queue individual scan task
        scan_user_vault.delay(user.id)
    
    return f"Scheduled scans for {users.count()} users"


# =============================================================================
# Genetic Password Evolution Tasks
# =============================================================================

@shared_task
def check_genetic_evolution(user_id: int):
    """
    Check if a user's genetic password should evolve based on epigenetic changes.
    
    This task fetches the latest biological age from connected epigenetic providers
    and triggers evolution if significant changes are detected.
    
    Args:
        user_id: ID of the user to check
        
    Returns:
        dict: Evolution status and results
    """
    from ..models import DNAConnection, GeneticEvolutionLog, GeneticSubscription
    from ..services.epigenetic_service import epigenetic_evolution_manager
    
    try:
        user = User.objects.get(id=user_id)
        
        # Check if user has a DNA connection
        try:
            dna_connection = DNAConnection.objects.get(user=user, is_active=True)
        except DNAConnection.DoesNotExist:
            logger.info(f"No active DNA connection for user {user_id}")
            return {'checked': False, 'reason': 'no_dna_connection'}
        
        # Check subscription for epigenetic features
        try:
            subscription = GeneticSubscription.objects.get(user=user)
            if not subscription.epigenetic_evolution_enabled:
                logger.info(f"Epigenetic evolution disabled for user {user_id}")
                return {'checked': False, 'reason': 'evolution_disabled'}
        except GeneticSubscription.DoesNotExist:
            logger.info(f"No subscription for user {user_id}")
            return {'checked': False, 'reason': 'no_subscription'}
        
        # Check for evolution
        result = epigenetic_evolution_manager.check_and_evolve(user)
        
        if result.get('evolved'):
            logger.info(
                f"Evolution triggered for user {user_id}: "
                f"Gen {result.get('old_generation')} -> {result.get('new_generation')}"
            )
            
            # Update the DNA connection
            dna_connection.evolution_generation = result.get('new_generation', 1)
            dna_connection.last_biological_age = result.get('biological_age')
            dna_connection.last_epigenetic_update = timezone.now()
            dna_connection.save()
            
            # Log the evolution (idempotent: dedup by user + generation + date)
            today = timezone.now().date()
            evo_dedup_key = f"evo_dedup:{user_id}:{result.get('new_generation')}:{today}"
            if not cache.get(evo_dedup_key):
                GeneticEvolutionLog.objects.create(
                    user=user,
                    trigger_type='automatic',
                    old_evolution_gen=result.get('old_generation', 1),
                    new_evolution_gen=result.get('new_generation', 2),
                    biological_age_before=result.get('previous_age'),
                    biological_age_after=result.get('biological_age'),
                    success=True,
                    completed_at=timezone.now()
                )
                cache.set(evo_dedup_key, True, 86400)  # 24h TTL
            else:
                logger.info(f"Evolution log deduplicated for user {user_id}")
            
            # Update subscription usage
            subscription.evolutions_triggered = (subscription.evolutions_triggered or 0) + 1
            subscription.save()
            
            return {
                'checked': True,
                'evolved': True,
                'old_generation': result.get('old_generation'),
                'new_generation': result.get('new_generation'),
                'biological_age': result.get('biological_age'),
            }
        
        return {
            'checked': True,
            'evolved': False,
            'current_generation': dna_connection.evolution_generation,
            'reason': 'no_significant_change',
        }
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {'checked': False, 'error': 'user_not_found'}
    
    except Exception as e:
        logger.error(f"Error checking genetic evolution for user {user_id}: {str(e)}")
        return {'checked': False, 'error': str(e)}


@shared_task
def daily_genetic_evolution_check():
    """
    Daily scheduled task to check all eligible users for genetic password evolution.
    
    This runs once daily and queues individual evolution checks for users with:
    - Active DNA connections
    - Epigenetic evolution enabled
    - Premium or trial subscription
    """
    from ..models import DNAConnection, GeneticSubscription
    
    # Find users with active DNA connections and epigenetic features
    eligible_connections = DNAConnection.objects.filter(
        is_active=True,
        user__geneticsubscription__epigenetic_evolution_enabled=True,
        user__geneticsubscription__status='active',
    ).select_related('user')
    
    queued_count = 0
    
    for connection in eligible_connections:
        # Queue individual evolution check
        check_genetic_evolution.delay(connection.user_id)
        queued_count += 1
    
    logger.info(f"Queued genetic evolution checks for {queued_count} users")
    return {'queued': queued_count}


@shared_task
def sync_epigenetic_data(user_id: int, provider: str = None):
    """
    Sync epigenetic data from connected providers for a user.
    
    This fetches the latest biological age and other epigenetic markers
    from providers like Humanity.health.
    
    Args:
        user_id: ID of the user
        provider: Optional specific provider to sync from
        
    Returns:
        dict: Sync results including biological age data
    """
    from ..models import DNAConnection
    from ..services.epigenetic_service import HumanityHealthProvider, ManualEpigeneticProvider
    
    try:
        user = User.objects.get(id=user_id)
        
        try:
            dna_connection = DNAConnection.objects.get(user=user, is_active=True)
        except DNAConnection.DoesNotExist:
            return {'synced': False, 'reason': 'no_connection'}
        
        # Try to fetch from Humanity.health if no specific provider
        epigenetic_provider = HumanityHealthProvider()
        
        try:
            # This would use the user's OAuth token that's stored with the connection
            # For now, we'll return a placeholder result
            result = {
                'synced': True,
                'provider': 'humanity_health',
                'biological_age': None,  # Would be fetched from API
                'message': 'Epigenetic sync queued - API integration pending',
            }
            
            logger.info(f"Epigenetic sync completed for user {user_id}")
            return result
            
        except Exception as api_error:
            logger.warning(f"API sync failed for user {user_id}: {api_error}")
            return {
                'synced': False,
                'error': str(api_error),
            }
            
    except User.DoesNotExist:
        return {'synced': False, 'error': 'user_not_found'}
    
    except Exception as e:
        logger.error(f"Error syncing epigenetic data for user {user_id}: {str(e)}")
        return {'synced': False, 'error': str(e)}


@shared_task
def cleanup_expired_genetic_trials():
    """
    Daily task to clean up expired genetic password trials.
    
    - Marks expired trials as inactive
    - Disables epigenetic features for expired subscriptions
    - Sends notification to users about trial expiration
    """
    from ..models import GeneticSubscription
    
    now = timezone.now()
    
    # Find expired trials
    expired_trials = GeneticSubscription.objects.filter(
        tier='trial',
        status='active',
        trial_expires_at__lt=now,
    )
    
    expired_count = 0
    
    for subscription in expired_trials:
        subscription.status = 'expired'
        subscription.epigenetic_evolution_enabled = False
        subscription.save()
        
        # TODO: Send notification to user
        # notification_service.send_trial_expired(subscription.user)
        
        expired_count += 1
        logger.info(f"Expired trial for user {subscription.user_id}")
    
    logger.info(f"Cleaned up {expired_count} expired genetic trials")
    return {'expired_trials_cleaned': expired_count}


@shared_task
def refresh_dna_tokens():
    """
    Weekly task to refresh OAuth tokens for DNA providers.
    
    Refreshes tokens that are about to expire to maintain access
    to DNA provider APIs.
    """
    from ..models import DNAConnection
    from ..services.dna_provider_service import get_dna_provider
    
    # Find connections with tokens that might need refresh
    # (tokens typically expire after a certain period)
    active_connections = DNAConnection.objects.filter(
        is_active=True,
        status='connected',
    )
    
    refreshed_count = 0
    failed_count = 0
    
    for connection in active_connections:
        try:
            provider = get_dna_provider(connection.provider)
            
            if connection.encrypted_refresh_token:
                # Decrypt and refresh token
                # This is a placeholder - actual implementation would decrypt
                # and call the provider's refresh endpoint
                
                logger.debug(f"Token refresh queued for user {connection.user_id}")
                refreshed_count += 1
                
        except Exception as e:
            logger.error(
                f"Failed to refresh token for user {connection.user_id}: {str(e)}"
            )
            failed_count += 1
    
    logger.info(f"Token refresh complete: {refreshed_count} refreshed, {failed_count} failed")
    return {
        'refreshed': refreshed_count,
        'failed': failed_count,
    }


# =============================================================================
# 🔮 Predictive Password Expiration Tasks
# =============================================================================

@shared_task
def analyze_user_password_patterns(user_id: int):
    """
    Analyze all of a user's passwords to build pattern fingerprints.
    
    Updates the user's PasswordPatternProfile with aggregated pattern
    analysis data for vulnerability assessment.
    
    Args:
        user_id: ID of the user to analyze
        
    Returns:
        dict: Analysis results
    """
    from ..models import PasswordPatternProfile
    from ..services.predictive_expiration_service import get_predictive_expiration_service
    from ..services.pattern_analysis_engine import get_pattern_analysis_engine
    
    try:
        user = User.objects.get(id=user_id)
        service = get_predictive_expiration_service()
        pattern_engine = get_pattern_analysis_engine()
        
        # Get or create profile
        profile, created = PasswordPatternProfile.objects.get_or_create(user=user)
        
        # Get user's vault items
        try:
            vault_items = EncryptedVaultItem.objects.filter(
                user=user,
                item_type='password'
            )
        except Exception:
            vault_items = []
        
        # Aggregate statistics
        total_analyzed = 0
        weak_patterns = 0
        char_distributions = []
        lengths = []
        has_dict_base = 0
        has_keyboard = 0
        has_dates = 0
        has_leet = 0
        
        for item in vault_items:
            try:
                password = item.get_decrypted_password(user)
                if not password:
                    continue
                
                # Analyze pattern
                pattern = pattern_engine.analyze_password(password)
                total_analyzed += 1
                
                # Track statistics
                lengths.append(pattern.length)
                char_dist = pattern_engine.get_char_class_distribution(password)
                char_distributions.append(char_dist)
                
                if pattern.has_dictionary_base:
                    has_dict_base += 1
                if pattern.keyboard_patterns:
                    has_keyboard += 1
                if pattern.date_patterns:
                    has_dates += 1
                if 'leet' in pattern.mutations:
                    has_leet += 1
                
                # Check for weak patterns
                if pattern.entropy_estimate < 40 or pattern.has_dictionary_base:
                    weak_patterns += 1
                    
            except Exception as e:
                logger.debug(f"Could not analyze vault item: {e}")
                continue
        
        # Update profile
        if total_analyzed > 0:
            profile.total_passwords_analyzed = total_analyzed
            profile.weak_patterns_detected = weak_patterns
            profile.avg_password_length = sum(lengths) / len(lengths)
            profile.min_length_used = min(lengths) if lengths else 0
            profile.max_length_used = max(lengths) if lengths else 0
            profile.uses_common_base_words = has_dict_base > 0
            profile.uses_keyboard_patterns = has_keyboard > 0
            profile.uses_date_patterns = has_dates > 0
            profile.uses_leet_substitutions = has_leet > 0
            profile.overall_pattern_risk_score = weak_patterns / total_analyzed
            
            # Aggregate char class distributions
            if char_distributions:
                avg_dist = {}
                for key in ['L', 'U', 'D', 'S']:
                    values = [d.get(key, 0) for d in char_distributions]
                    avg_dist[key] = sum(values) / len(values)
                profile.char_class_distribution = avg_dist
            
            # Calculate length variance
            if len(lengths) > 1:
                mean_len = profile.avg_password_length
                variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
                profile.length_variance = variance
        
        profile.last_analysis_at = timezone.now()
        profile.save()
        
        logger.info(f"Pattern analysis complete for user {user_id}: "
                   f"{total_analyzed} analyzed, {weak_patterns} weak")
        
        return {
            'user_id': user_id,
            'analyzed': total_analyzed,
            'weak_patterns': weak_patterns,
            'risk_score': profile.overall_pattern_risk_score,
        }
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {'error': 'user_not_found'}
    except Exception as e:
        logger.error(f"Error analyzing patterns for user {user_id}: {e}")
        return {'error': str(e)}


@shared_task(name='security.tasks.update_threat_intelligence')
def update_threat_intelligence():
    """
    Ingest threat intelligence from all active feeds via pluggable adapters.

    Each feed is dispatched to its adapter (HIBP, internal dark-web, or a
    graceful no-op for unconfigured feeds). Recent-breach pressure per industry
    is aggregated across feeds and written to IndustryThreatLevel.

    Returns:
        dict: Update statistics
    """
    from ..models import ThreatIntelFeed, IndustryThreatLevel
    from ..services.threat_feed_adapters import get_feed_adapter

    feeds = ThreatIntelFeed.objects.filter(is_active=True)

    updated_count = 0
    failed_count = 0
    total_items = 0
    # Aggregate recent-breach pressure per industry across all feeds.
    industry_totals = {}

    for feed in feeds:
        adapter = get_feed_adapter(feed.feed_type)
        try:
            result = adapter.fetch(feed)
        except Exception as e:
            # Adapters are meant to degrade gracefully; treat a raise as a
            # failed sync rather than crashing the whole task.
            logger.error(f"Feed {feed.name} adapter crashed: {e}")
            result = None

        if result is None or not result.ok:
            feed.last_sync_at = timezone.now()
            feed.last_sync_success = False
            feed.is_healthy = False
            feed.health_check_message = (
                result.message if result else 'adapter error'
            )[:500]
            feed.save()
            failed_count += 1
            continue

        feed.last_sync_at = timezone.now()
        feed.last_sync_success = True
        feed.is_healthy = True
        feed.health_check_message = result.message[:500]
        feed.last_sync_items_count = result.items_count
        feed.total_items_ingested = (feed.total_items_ingested or 0) + result.items_count
        feed.save()

        updated_count += 1
        total_items += result.items_count
        for industry, count in result.industry_signals.items():
            industry_totals[industry] = industry_totals.get(industry, 0) + count
        logger.info(f"Synced threat feed {feed.name}: {result.message}")

    industries_updated = _apply_industry_signals(IndustryThreatLevel, industry_totals)

    logger.info(
        f"Threat intel update complete: {updated_count} feeds updated, "
        f"{failed_count} failed, {total_items} items, "
        f"{industries_updated} industries refreshed"
    )

    return {
        'feeds_updated': updated_count,
        'feeds_failed': failed_count,
        'items_ingested': total_items,
        'industries_updated': industries_updated,
    }


def _apply_industry_signals(IndustryThreatLevel, industry_totals):
    """Upsert IndustryThreatLevel rows from aggregated recent-breach counts."""
    def _score(count):
        return min(count / 20.0, 1.0)

    def _level(score):
        if score >= 0.8:
            return 'critical'
        if score >= 0.6:
            return 'severe'
        if score >= 0.4:
            return 'high'
        if score >= 0.2:
            return 'elevated'
        return 'low'

    updated = 0
    for industry, count in industry_totals.items():
        score = _score(count)
        IndustryThreatLevel.objects.update_or_create(
            industry_code=industry,
            defaults={
                'industry_name': industry.replace('_', ' ').title(),
                'recent_breaches_count': count,
                'threat_score': score,
                'current_threat_level': _level(score),
            },
        )
        updated += 1

    # Keep the recency window accurate: clear breach pressure for industries
    # that previously had recent breaches but none in the current feed result.
    # Only touch rows this task drove (recent_breaches_count > 0) so any
    # admin-managed posture is left alone.
    stale = IndustryThreatLevel.objects.filter(
        recent_breaches_count__gt=0,
    ).exclude(industry_code__in=industry_totals.keys())
    updated += stale.update(
        recent_breaches_count=0,
        threat_score=0.0,
        current_threat_level='low',
    )
    return updated


@shared_task(name='security.tasks.evaluate_password_expiration_risk')
def evaluate_password_expiration_risk(credential_id: str, user_id: int):
    """
    Re-score compromise risk for a credential from its stored fingerprint.

    Zero-knowledge: this task never decrypts the vault. It re-scores the
    existing PredictiveExpirationRule (whose structural fingerprint was
    uploaded by the browser via the fingerprints/ endpoint) against the
    current threat intelligence. If no fingerprint has been uploaded yet,
    there is nothing to score and the task is a no-op.

    Args:
        credential_id: Identifier of the credential
        user_id: ID of the user

    Returns:
        dict: Risk evaluation results
    """
    from ..models import PredictiveExpirationRule
    from ..services.predictive_expiration_service import get_predictive_expiration_service

    try:
        user = User.objects.get(id=user_id)
        service = get_predictive_expiration_service()

        # The fingerprint must already exist (uploaded client-side). No rule
        # means the browser hasn't synced this credential yet.
        try:
            rule = PredictiveExpirationRule.objects.get(
                user=user,
                credential_id=str(credential_id),
            )
        except PredictiveExpirationRule.DoesNotExist:
            return {'status': 'no_fingerprint', 'credential_id': str(credential_id)}

        # Advance the stored age by the time elapsed since the last evaluation
        # so age-based thresholds (180/365 days) still cross between client
        # re-uploads. The browser overwrites this on its next sync.
        credential_age_days = rule.credential_age_days
        if rule.last_evaluated_at:
            elapsed_days = (timezone.now().date() - rule.last_evaluated_at.date()).days
            credential_age_days += max(0, elapsed_days)

        # Re-score from the stored structural metadata — no plaintext needed.
        rule = service.create_expiration_rule_from_fingerprint(
            user_id=user_id,
            credential_id=rule.credential_id,
            credential_domain=rule.credential_domain,
            domain_class=rule.domain_class,
            char_class_sequence=rule.char_class_sequence,
            length_bucket=rule.length_bucket,
            entropy_band=rule.entropy_band,
            has_dictionary_base=rule.has_dictionary_base,
            has_keyboard_pattern=rule.has_keyboard_pattern,
            has_date_pattern=rule.has_date_pattern,
            has_leet=rule.has_leet,
            credential_age_days=credential_age_days,
        )

        logger.info(f"Re-scored credential {credential_id} for user {user_id}: "
                   f"{rule.risk_level} risk ({rule.risk_score:.2f})")

        return {
            'credential_id': str(credential_id),
            'risk_level': rule.risk_level,
            'risk_score': rule.risk_score,
            'recommended_action': rule.recommended_action,
        }

    except User.DoesNotExist:
        return {'error': 'user_not_found'}
    except Exception as e:
        logger.error(f"Error evaluating credential {credential_id}: {e}")
        return {'error': str(e)}


@shared_task
def process_forced_rotation(credential_id: str, user_id: int, reason: str):
    """
    Execute proactive password rotation for a credential.
    
    Creates a rotation event and marks the expiration rule as acknowledged.
    
    Args:
        credential_id: UUID of the credential
        user_id: ID of the user
        reason: Reason for the rotation
        
    Returns:
        dict: Rotation results
    """
    from ..models import PredictiveExpirationRule, PasswordRotationEvent
    
    try:
        user = User.objects.get(id=user_id)
        
        # Get the expiration rule
        try:
            rule = PredictiveExpirationRule.objects.get(
                user=user,
                credential_id=credential_id
            )
        except PredictiveExpirationRule.DoesNotExist:
            return {'error': 'rule_not_found'}
        
        # Create rotation event (idempotent: dedup by credential + user + date)
        today = timezone.now().date()
        rotation_dedup_key = f"rotation_dedup:{credential_id}:{user_id}:{today}"
        
        if cache.get(rotation_dedup_key):
            logger.info(f"Rotation event deduplicated for credential {credential_id}")
            return {
                'credential_id': str(credential_id),
                'status': 'deduplicated',
            }
        
        event = PasswordRotationEvent.objects.create(
            user=user,
            credential_id=rule.credential_id,
            credential_domain=rule.credential_domain,
            rotation_type='proactive',
            outcome='pending',
            triggered_by_rule=rule,
            trigger_reason=reason,
            threat_factors_at_rotation=rule.threat_factors,
            risk_score_at_rotation=rule.risk_score,
        )
        cache.set(rotation_dedup_key, True, 86400)  # 24h TTL
        
        # Mark rule as acknowledged
        rule.user_acknowledged = True
        rule.user_acknowledged_at = timezone.now()
        rule.last_notification_sent = timezone.now()
        rule.notification_count += 1
        rule.save()
        
        logger.info(f"Processed forced rotation for credential {credential_id}")
        
        return {
            'event_id': str(event.event_id),
            'credential_id': str(credential_id),
            'status': 'pending',
        }
        
    except User.DoesNotExist:
        return {'error': 'user_not_found'}
    except Exception as e:
        logger.error(f"Error processing rotation for {credential_id}: {e}")
        return {'error': str(e)}


@shared_task(bind=True, name='security.tasks.daily_predictive_scan')
def daily_predictive_scan(self):
    """
    Daily zero-knowledge re-score of stored credential fingerprints.

    Refreshes threat intelligence first (so the re-score runs on current
    IndustryThreatLevel/actor data), then re-scores the fingerprints the
    browser already uploaded. The server never decrypts the vault — it only
    refreshes risk on stored structural metadata.
    """
    from celery import chord
    from ..models import PredictiveExpirationSettings, PredictiveExpirationRule

    # Refresh threat intel in-process first so the scan is always tied to a
    # fresh ingest rather than a wall-clock-offset beat that could lag/fail.
    # A refresh failure must not abort the scan — fall back to existing intel.
    try:
        update_threat_intelligence()
    except Exception:
        logger.exception("Threat-intel refresh failed; scanning on existing data")

    settings = PredictiveExpirationSettings.objects.filter(is_enabled=True)

    total_users = 0
    scan_failures = 0
    rescore_sigs = []

    for user_settings in settings:
        user_id = user_settings.user_id

        # Coarse-class exclusions only: under zero-knowledge the server holds
        # no exact domains, so exclude_domains is matched by normalized equality
        # against the coarse class. Exact-domain exclusion is enforced
        # client-side at upload time.
        excluded_classes = {
            d.strip().lower() for d in user_settings.exclude_domains if d
        }

        try:
            rules = PredictiveExpirationRule.objects.filter(
                user_id=user_id,
                is_active=True,
            )

            for rule in rules:
                if rule.domain_class and rule.domain_class.lower() in excluded_classes:
                    continue

                # Immutable signature: re-score from the stored fingerprint.
                rescore_sigs.append(
                    evaluate_password_expiration_risk.si(rule.credential_id, user_id)
                )

        except Exception:
            scan_failures += 1
            logger.exception("Error scanning predictive rules for user %s", user_id)
            continue

        total_users += 1

    total_credentials = len(rescore_sigs)

    # Don't notify on an incomplete scan: send_expiration_notifications is
    # global, so if any user's rules were never queued for re-score it could
    # fire on stale risk state. Skip the dispatch and let the next run retry;
    # per-credential re-scores still happen via the client ingest path.
    if scan_failures:
        logger.error(
            "Daily predictive scan incomplete: %s user(s) failed; "
            "skipping notification dispatch",
            scan_failures,
        )
        return {
            'users_scanned': total_users,
            'credentials_queued': total_credentials,
            'scan_failures': scan_failures,
            'notifications_dispatched': False,
        }

    # Completion handoff: fan out every re-score, then send notifications only
    # once they have ALL finished — so we never notify before the re-score
    # queue drains and miss newly high-risk credentials. With nothing to
    # re-score, send notifications directly.
    if rescore_sigs:
        chord(rescore_sigs)(send_expiration_notifications.si())
    else:
        send_expiration_notifications.delay()

    logger.info(
        f"Daily predictive scan complete: "
        f"{total_users} users, {total_credentials} fingerprints re-queued"
    )

    return {
        'users_scanned': total_users,
        'credentials_queued': total_credentials,
        'scan_failures': 0,
        'notifications_dispatched': True,
    }


def _send_ws_risk_alert(user_id, credential_id, credential_domain,
                        risk_level, risk_score):
    """Push a real-time risk alert to the user's WebSocket group.

    Best-effort: any failure (no channel layer configured, send error) is
    logged and swallowed so notification delivery never breaks the task.
    """
    try:
        from asgiref.sync import async_to_sync
        from ..consumers.predictive_expiration_consumer import send_risk_alert

        async_to_sync(send_risk_alert)(
            user_id=user_id,
            credential_id=credential_id,
            credential_domain=credential_domain,
            risk_level=risk_level,
            risk_score=risk_score,
        )
    except Exception as e:
        logger.warning(f"WS risk alert for user {user_id} not delivered: {e}")


@shared_task(name='security.tasks.send_expiration_notifications')
def send_expiration_notifications():
    """
    Send notifications to users with high-risk credentials.
    
    Sends email/push notifications for credentials that require
    attention based on their risk scores.
    """
    from ..models import PredictiveExpirationRule, PredictiveExpirationSettings
    from django.core.mail import send_mail
    from django.conf import settings
    from django.db import models
    
    # Get high-risk rules not yet notified today
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    high_risk_rules = PredictiveExpirationRule.objects.filter(
        is_active=True,
        user_acknowledged=False,
        risk_level__in=['high', 'critical'],
    ).filter(
        models.Q(last_notification_sent__lt=today_start) |
        models.Q(last_notification_sent__isnull=True)
    ).select_related('user')
    
    notifications_sent = 0
    
    for rule in high_risk_rules:
        try:
            # Check user's notification preferences
            try:
                user_settings = PredictiveExpirationSettings.objects.get(
                    user=rule.user
                )
                
                if rule.risk_level == 'high' and not user_settings.notify_on_high_risk:
                    continue
                if rule.risk_level == 'critical' and not user_settings.notify_on_high_risk:
                    continue
                    
            except PredictiveExpirationSettings.DoesNotExist:
                pass
            
            # Fan out a real-time risk alert over the WebSocket (best-effort:
            # a missing/!configured channel layer must not fail the task).
            _send_ws_risk_alert(
                user_id=rule.user_id,
                credential_id=rule.credential_id,
                credential_domain=rule.credential_domain,
                risk_level=rule.risk_level,
                risk_score=rule.risk_score,
            )

            # Update rule
            rule.last_notification_sent = timezone.now()
            rule.notification_count += 1
            rule.save()

            notifications_sent += 1
            
        except Exception as e:
            logger.error(f"Error sending notification for rule {rule.rule_id}: {e}")
    
    logger.info(f"Sent {notifications_sent} expiration notifications")
    
    return {'notifications_sent': notifications_sent}
