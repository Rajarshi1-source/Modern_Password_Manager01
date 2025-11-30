"""
Celery Tasks for ML-Powered Dark Web Monitoring
Handles async processing of breach detection, credential matching, and alerts
"""

from celery import shared_task, group, chord
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
import logging
import json
from typing import List, Dict

from .models import (
    BreachSource, MLBreachData, UserCredentialMonitoring,
    MLBreachMatch, DarkWebScrapeLog, BreachPatternAnalysis
)
from .ml_services import get_breach_classifier, get_credential_matcher
from vault.models import BreachAlert
from .ml_config import MLDarkWebConfig

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(bind=True, max_retries=3)
def process_scraped_content(self, content: str, source_id: int, content_metadata: dict = None):
    """
    Process scraped dark web content with ML classifier
    
    Args:
        content: Raw scraped content
        source_id: ID of the BreachSource
        content_metadata: Additional metadata about the content
    """
    try:
        logger.info(f"Processing content from source {source_id}")
        
        # Get the breach classifier
        classifier = get_breach_classifier()
        
        # Classify the content
        result = classifier.classify_breach(content)
        
        # Extract indicators
        indicators = classifier.extract_breach_indicators(content)
        
        if result['is_breach']:
            # Get source
            source = BreachSource.objects.get(id=source_id)
            
            # Create breach record
            breach_id = f"BREACH_{timezone.now().timestamp():.0f}_{source.id}"
            
            breach = MLBreachData.objects.create(
                breach_id=breach_id,
                title=content[:500].strip(),
                description=content[:2000].strip(),
                source=source,
                severity=result['severity'],
                confidence_score=result['confidence'],
                ml_model_version=MLDarkWebConfig.CURRENT_MODEL_VERSION,
                raw_content=content,
                processed_content=content[:5000],
                processing_status='analyzing',
                extracted_emails=indicators.get('emails', []),
                extracted_domains=indicators.get('domains', []),
                extracted_credentials=indicators.get('credentials', [])
            )
            
            logger.info(f"Breach detected: {breach.breach_id} (confidence: {result['confidence']:.2f})")
            
            # Trigger credential matching async
            match_credentials_against_breach.delay(breach.id)
            
            # Update source reliability
            update_source_reliability.delay(source_id, success=True)
            
            return {
                'success': True,
                'breach_id': breach.id,
                'severity': result['severity'],
                'confidence': result['confidence']
            }
        else:
            logger.info(f"No breach detected in content from source {source_id}")
            return {
                'success': True,
                'breach_id': None,
                'message': 'No breach detected'
            }
    
    except BreachSource.DoesNotExist:
        logger.error(f"BreachSource {source_id} not found")
        return {'success': False, 'error': 'Source not found'}
    
    except Exception as e:
        logger.error(f"Error processing content: {e}", exc_info=True)
        # Retry with exponential backoff
        self.retry(exc=e, countdown=2 ** self.request.retries * 60)


@shared_task(bind=True)
def match_credentials_against_breach(self, breach_id: int):
    """
    Match user credentials against detected breach
    Uses Siamese network for similarity matching
    
    Args:
        breach_id: ID of the MLBreachData record
    """
    try:
        logger.info(f"Matching credentials against breach {breach_id}")
        
        # Get breach
        breach = MLBreachData.objects.get(id=breach_id)
        
        # Extract credentials from breach
        breach_credentials = breach.extracted_credentials or []
        breach_emails = breach.extracted_emails or []
        
        # Combine for matching
        all_breach_identifiers = list(set(breach_credentials + breach_emails))
        
        if not all_breach_identifiers:
            logger.warning(f"No identifiers found in breach {breach_id}")
            breach.processing_status = 'completed'
            breach.processed_at = timezone.now()
            breach.save()
            return {'success': True, 'matches': 0}
        
        # Get credential matcher
        matcher = get_credential_matcher()
        
        # Get all active monitored credentials
        monitored_credentials = UserCredentialMonitoring.objects.filter(is_active=True)
        
        matches_found = 0
        
        # Process in batches to avoid memory issues
        batch_size = MLDarkWebConfig.MATCH_BATCH_SIZE
        
        for i in range(0, monitored_credentials.count(), batch_size):
            batch = monitored_credentials[i:i + batch_size]
            
            for cred in batch:
                # Find matches
                credential_matches = matcher.find_matches(
                    cred.email_hash,
                    all_breach_identifiers
                )
                
                if credential_matches:
                    # Get best match
                    best_match = credential_matches[0]
                    similarity_score = best_match[1]
                    
                    # Create match record
                    match, created = MLBreachMatch.objects.get_or_create(
                        user=cred.user,
                        breach=breach,
                        monitored_credential=cred,
                        defaults={
                            'similarity_score': similarity_score,
                            'confidence_score': similarity_score * breach.confidence_score,
                            'match_type': 'email' if '@' in best_match[0] else 'credential',
                            'matched_data': {
                                'matched_identifier': best_match[0][:50],  # Truncate for privacy
                                'num_matches': len(credential_matches)
                            }
                        }
                    )
                    
                    if created:
                        matches_found += 1
                        logger.info(f"Match found: User {cred.user.id} - Breach {breach_id} (similarity: {similarity_score:.2f})")
                        
                        # Create alert async
                        create_breach_alert.delay(match.id)
                
                # Update last checked
                cred.last_checked = timezone.now()
                cred.save(update_fields=['last_checked'])
        
        # Update breach status
        breach.processing_status = 'matched' if matches_found > 0 else 'completed'
        breach.processed_at = timezone.now()
        breach.affected_records = matches_found
        breach.save()
        
        logger.info(f"Credential matching completed for breach {breach_id}. {matches_found} matches found.")
        
        return {
            'success': True,
            'breach_id': breach_id,
            'matches': matches_found
        }
    
    except MLBreachData.DoesNotExist:
        logger.error(f"Breach {breach_id} not found")
        return {'success': False, 'error': 'Breach not found'}
    
    except Exception as e:
        logger.error(f"Error matching credentials: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task
def create_breach_alert(match_id: int):
    """
    Create and send breach alert to user
    
    Args:
        match_id: ID of the MLBreachMatch record
    """
    try:
        match = MLBreachMatch.objects.select_related('user', 'breach', 'monitored_credential').get(id=match_id)
        
        # Check if alert already created
        if match.alert_created:
            logger.warning(f"Alert already created for match {match_id}")
            return {'success': True, 'message': 'Alert already exists'}
        
        # Create BreachAlert
        alert = BreachAlert.objects.create(
            user=match.user,
            breach_name=match.breach.title[:255],
            breach_date=match.breach.breach_date.date() if match.breach.breach_date else timezone.now().date(),
            breach_description=match.breach.description[:1000],
            data_type='email',  # or determine from match_type
            identifier=match.monitored_credential.domain,
            exposed_data={
                'types': match.breach.exposed_data_types,
                'severity': match.breach.severity,
                'confidence': match.confidence_score
            },
            severity=match.breach.severity.lower(),
            detected_at=match.detected_at,
            notified=False
        )
        
        # Update match record
        match.alert_created = True
        match.alert_id = alert.id
        match.save()
        
        logger.info(f"Alert created: {alert.id} for user {match.user.id}")
        
        # Send notification
        send_breach_notification.delay(alert.id)
        
        return {
            'success': True,
            'alert_id': alert.id
        }
    
    except MLBreachMatch.DoesNotExist:
        logger.error(f"Match {match_id} not found")
        return {'success': False, 'error': 'Match not found'}
    
    except Exception as e:
        logger.error(f"Error creating alert: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task
def send_breach_notification(alert_id: int):
    """
    Send real-time notification to user via WebSocket
    
    Args:
        alert_id: ID of the BreachAlert
    """
    try:
        alert = BreachAlert.objects.select_related('user').get(id=alert_id)
        
        # Send via Django Channels WebSocket
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"user_{alert.user.id}",
                {
                    'type': 'breach_alert',
                    'message': {
                        'alert_id': alert.id,
                        'breach_name': alert.breach_name,
                        'severity': alert.severity,
                        'detected_at': alert.detected_at.isoformat(),
                        'description': alert.breach_description[:200]
                    }
                }
            )
            
            logger.info(f"WebSocket notification sent to user {alert.user.id}")
        else:
            logger.warning("Channel layer not configured. Notification not sent.")
        
        # Mark as notified
        alert.notified = True
        alert.notification_sent_at = timezone.now()
        alert.save()
        
        # Optional: Send email notification
        # send_email_notification.delay(alert_id)
        
        return {'success': True}
    
    except BreachAlert.DoesNotExist:
        logger.error(f"Alert {alert_id} not found")
        return {'success': False, 'error': 'Alert not found'}
    
    except Exception as e:
        logger.error(f"Error sending notification: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task
def broadcast_alert_update(user_id: int, alert_id: int, update_type: str, additional_data: dict = None):
    """
    Broadcast real-time alert status updates to user via WebSocket
    
    Args:
        user_id: ID of the User
        alert_id: ID of the BreachAlert
        update_type: Type of update ('marked_read', 'resolved', 'dismissed', etc.)
        additional_data: Optional additional data to send
    """
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        
        if not channel_layer:
            logger.warning("Channel layer not configured. Alert update not broadcast.")
            return {'success': False, 'error': 'Channel layer not configured'}
        
        # Prepare message
        message = {
            'alert_id': alert_id,
            'update_type': update_type,
            'timestamp': timezone.now().isoformat()
        }
        
        if additional_data:
            message.update(additional_data)
        
        # Send via WebSocket
        async_to_sync(channel_layer.group_send)(
            f"user_{user_id}",
            {
                'type': 'alert_update',
                'message': message
            }
        )
        
        logger.info(f"Alert update broadcast to user {user_id}: {update_type}")
        
        return {'success': True}
    
    except Exception as e:
        logger.error(f"Error broadcasting alert update: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task
def scrape_dark_web_source(source_id: int):
    """
    Scrape a dark web source for breach data using Scrapy
    
    Args:
        source_id: ID of the BreachSource
    """
    try:
        source = BreachSource.objects.get(id=source_id, is_active=True)
        
        # Create scrape log
        scrape_log = DarkWebScrapeLog.objects.create(
            source=source,
            status='running'
        )
        
        logger.info(f"Starting scrape of {source.name}")
        
        # Import Scrapy components
        from scrapy.crawler import CrawlerProcess
        from scrapy.utils.project import get_project_settings
        from .scrapers.dark_web_spider import (
            BreachForumSpider,
            PastebinSpider,
            GenericDarkWebSpider,
            SCRAPY_SETTINGS
        )
        
        # Determine spider type based on source type
        spider_map = {
            'forum': BreachForumSpider,
            'pastebin': PastebinSpider,
            'marketplace': GenericDarkWebSpider,
            'telegram': GenericDarkWebSpider,
            'other': GenericDarkWebSpider
        }
        
        spider_class = spider_map.get(source.source_type, GenericDarkWebSpider)
        
        # Configure Scrapy settings
        settings = SCRAPY_SETTINGS.copy()
        settings.update({
            'FEEDS': {
                f'/tmp/scrape_{source_id}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json': {
                    'format': 'json',
                    'overwrite': True,
                }
            }
        })
        
        # Initialize crawler
        process = CrawlerProcess(settings)
        
        # Add spider
        process.crawl(
            spider_class,
            url=source.url,
            use_tor=True,  # Always use Tor for dark web
            source_id=source_id
        )
        
        # Run spider (blocking)
        logger.info(f"Running spider for {source.name}")
        
        # Note: In production, use scrapyd or separate process for non-blocking execution
        try:
            import glob
            import json
            import os
            
            # Start crawling
            process.start()  # This will block until spider completes
            
            # Read scraped data from output file
            output_files = glob.glob(f'/tmp/scrape_{source_id}_*.json')
            
            scraped_content = []
            breaches_detected = 0
            
            if output_files:
                with open(output_files[0], 'r') as f:
                    scraped_items = json.load(f)
                    scraped_content = scraped_items if isinstance(scraped_items, list) else [scraped_items]
                    
                    # Process each scraped item
                    for item in scraped_content:
                        # Send to ML processing
                        result = process_scraped_content.delay(
                            content=item.get('content', ''),
                            source_id=source_id,
                            content_metadata=item
                        )
                        
                        # Check if it's a breach
                        indicators = item.get('indicators', {})
                        if indicators.get('has_breach_keyword') or indicators.get('has_password_keyword'):
                            breaches_detected += 1
                
                # Clean up temp file
                os.remove(output_files[0])
                logger.info(f"Processed {len(scraped_content)} items from {source.name}")
            else:
                logger.warning(f"No output file found for scrape {source_id}")
                
        except Exception as e:
            logger.error(f"Error processing spider results: {e}", exc_info=True)
            scraped_content = []
            breaches_detected = 0
        
        # Update scrape log
        scrape_log.items_found = len(scraped_content)
        scrape_log.breaches_detected = breaches_detected
        scrape_log.status = 'completed'
        scrape_log.completed_at = timezone.now()
        scrape_log.processing_time_seconds = (scrape_log.completed_at - scrape_log.started_at).total_seconds()
        scrape_log.save()
        
        # Update source
        source.last_scraped = timezone.now()
        source.save()
        
        logger.info(f"Scrape completed: {source.name}. {breaches_detected} breaches detected.")
        
        return {
            'success': True,
            'source_id': source_id,
            'items_found': len(scraped_content),
            'breaches_detected': breaches_detected
        }
    
    except BreachSource.DoesNotExist:
        logger.error(f"Source {source_id} not found or inactive")
        return {'success': False, 'error': 'Source not found'}
    
    except Exception as e:
        logger.error(f"Error scraping source: {e}", exc_info=True)
        
        # Update scrape log
        if 'scrape_log' in locals():
            scrape_log.status = 'failed'
            scrape_log.error_message = str(e)
            scrape_log.completed_at = timezone.now()
            scrape_log.save()
        
        return {'success': False, 'error': str(e)}


@shared_task
def scrape_all_active_sources():
    """
    Scrape all active dark web sources
    Called periodically by Celery beat
    """
    logger.info("Starting scheduled scrape of all active sources")
    
    active_sources = BreachSource.objects.filter(is_active=True)
    
    # Create a group of scraping tasks
    job = group(scrape_dark_web_source.s(source.id) for source in active_sources)
    result = job.apply_async()
    
    logger.info(f"Initiated scraping for {active_sources.count()} sources")
    
    return {
        'success': True,
        'sources_count': active_sources.count(),
        'task_id': result.id
    }


@shared_task
def update_source_reliability(source_id: int, success: bool = True):
    """
    Update source reliability score based on scraping results
    
    Args:
        source_id: ID of the BreachSource
        success: Whether the scrape was successful
    """
    try:
        source = BreachSource.objects.get(id=source_id)
        
        # Update reliability score (exponential moving average)
        alpha = 0.1  # Weight for new observation
        new_observation = 1.0 if success else 0.0
        source.reliability_score = (alpha * new_observation) + ((1 - alpha) * source.reliability_score)
        source.save(update_fields=['reliability_score'])
        
        logger.info(f"Updated reliability for {source.name}: {source.reliability_score:.2f}")
        
        return {'success': True, 'reliability': source.reliability_score}
    
    except BreachSource.DoesNotExist:
        logger.error(f"Source {source_id} not found")
        return {'success': False, 'error': 'Source not found'}


@shared_task
def analyze_breach_patterns():
    """
    Analyze breach patterns using LSTM
    Detect temporal patterns, threat actors, etc.
    """
    # TODO: Implement LSTM pattern detection
    # This would analyze sequences of breaches over time
    # to detect patterns and predict future breaches
    
    logger.info("Breach pattern analysis started")
    
    try:
        # Get recent breaches
        recent_breaches = MLBreachData.objects.filter(
            detected_at__gte=timezone.now() - timezone.timedelta(days=30)
        ).order_by('detected_at')
        
        if recent_breaches.count() < 10:
            logger.info("Not enough data for pattern analysis")
            return {'success': True, 'message': 'Insufficient data'}
        
        # TODO: Implement LSTM model for pattern detection
        # For now, return placeholder
        
        logger.info(f"Analyzed {recent_breaches.count()} recent breaches")
        
        return {
            'success': True,
            'breaches_analyzed': recent_breaches.count()
        }
    
    except Exception as e:
        logger.error(f"Error analyzing patterns: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task
def cleanup_old_breach_data(days_to_keep: int = 365):
    """
    Clean up old breach data to maintain database performance
    
    Args:
        days_to_keep: Number of days of data to keep
    """
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days_to_keep)
        
        # Delete old breach data (keep alerts)
        deleted_breaches = MLBreachData.objects.filter(
            detected_at__lt=cutoff_date,
            processing_status='completed'
        ).delete()
        
        # Delete old scrape logs
        deleted_logs = DarkWebScrapeLog.objects.filter(
            started_at__lt=cutoff_date
        ).delete()
        
        logger.info(f"Cleanup completed: {deleted_breaches[0]} breaches, {deleted_logs[0]} logs deleted")
        
        return {
            'success': True,
            'breaches_deleted': deleted_breaches[0],
            'logs_deleted': deleted_logs[0]
        }
    
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task
def monitor_user_credentials(user_id: int, credentials: List[str]):
    """
    Add user credentials to monitoring system
    
    Args:
        user_id: ID of the user
        credentials: List of credentials (emails) to monitor
    """
    try:
        user = User.objects.get(id=user_id)
        matcher = get_credential_matcher()
        
        added_count = 0
        
        for credential in credentials:
            # Hash credential
            email_hash = matcher.hash_credential(credential)
            
            # Extract domain
            domain = credential.split('@')[-1] if '@' in credential else 'unknown'
            
            # Get embedding
            embedding = matcher.get_embedding(email_hash)
            
            # Create or update monitoring record
            monitoring, created = UserCredentialMonitoring.objects.get_or_create(
                user=user,
                email_hash=email_hash,
                defaults={
                    'domain': domain,
                    'email_embedding': embedding.tobytes(),
                    'is_active': True
                }
            )
            
            if created:
                added_count += 1
        
        logger.info(f"Added {added_count} credentials for monitoring (user: {user_id})")
        
        # Trigger immediate check against existing breaches
        check_user_against_all_breaches.delay(user_id)
        
        return {
            'success': True,
            'added': added_count
        }
    
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {'success': False, 'error': 'User not found'}
    
    except Exception as e:
        logger.error(f"Error monitoring credentials: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task
def check_user_against_all_breaches(user_id: int):
    """
    Check a user's credentials against all existing breaches
    Used when adding new monitoring or for periodic checks
    
    Args:
        user_id: ID of the user
    """
    try:
        user = User.objects.get(id=user_id)
        
        # Get user's monitored credentials
        monitored_creds = UserCredentialMonitoring.objects.filter(
            user=user,
            is_active=True
        )
        
        if not monitored_creds.exists():
            logger.info(f"No monitored credentials for user {user_id}")
            return {'success': True, 'message': 'No credentials to check'}
        
        # Get all unprocessed breaches
        breaches = MLBreachData.objects.filter(
            processing_status__in=['matched', 'completed']
        )
        
        matches_found = 0
        
        # Check against each breach
        for breach in breaches:
            result = match_credentials_against_breach.delay(breach.id)
            # The task will handle individual user matching
        
        logger.info(f"Initiated breach checks for user {user_id} against {breaches.count()} breaches")
        
        return {
            'success': True,
            'breaches_checked': breaches.count()
        }
    
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {'success': False, 'error': 'User not found'}
    
    except Exception as e:
        logger.error(f"Error checking breaches: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

