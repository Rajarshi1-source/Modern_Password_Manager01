"""
Analytics Celery Tasks
======================

Asynchronous processing for analytics data writes.
Moved out of the request/response cycle to avoid blocking API responses
and to absorb traffic spikes via celery queue backpressure.
"""

import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    name='analytics.tasks.process_analytics_batch',
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def process_analytics_batch(self, data: dict, user_id: int = None, client_ip: str = None):
    """
    Process a batch of analytics data asynchronously.

    Receives the full request payload and performs all DB writes
    outside the HTTP request/response cycle.

    Args:
        data: The analytics payload (events, engagements, conversions, session, performance)
        user_id: Authenticated user ID or None for anonymous
        client_ip: Client IP address (already anonymized)
    """
    from django.contrib.auth import get_user_model
    from .models import (
        AnalyticsEvent,
        UserEngagement,
        Conversion,
        UserSession,
        PerformanceMetric,
    )
    from datetime import timedelta

    User = get_user_model()

    try:
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f"Analytics: user {user_id} not found, recording as anonymous")

        counts = {'events': 0, 'engagements': 0, 'conversions': 0}

        # --- Process events ---
        for event_data in data.get('events', []):
            properties = event_data.get('properties', {})
            metadata = event_data.get('metadata', {})

            AnalyticsEvent.objects.create(
                name=event_data.get('name'),
                category=event_data.get('category', 'general'),
                user=user,
                session_id=properties.get('sessionId', ''),
                properties=properties,
                url=properties.get('url', ''),
                path=properties.get('path', ''),
                referrer=event_data.get('referrer', ''),
                user_agent=metadata.get('userAgent', ''),
                ip_address=client_ip,
                language=metadata.get('language', ''),
                platform=metadata.get('platform', ''),
                timestamp=timezone.now(),
            )
            counts['events'] += 1

        # --- Process engagements ---
        for engagement_data in data.get('engagements', []):
            properties = engagement_data.get('properties', {})
            UserEngagement.objects.create(
                user=user,
                session_id=engagement_data.get('sessionId', ''),
                metric=engagement_data.get('metric'),
                value=engagement_data.get('value', 0),
                properties=properties,
                timestamp=timezone.now(),
            )
            counts['engagements'] += 1

        # --- Process conversions ---
        for conversion_data in data.get('conversions', []):
            properties = conversion_data.get('properties', {})
            Conversion.objects.create(
                user=user,
                session_id=conversion_data.get('sessionId', ''),
                name=conversion_data.get('name'),
                value=conversion_data.get('value', 0),
                properties=properties,
                timestamp=timezone.now(),
            )
            counts['conversions'] += 1

        # --- Process session data ---
        session_data = data.get('session', {})
        session_id = session_data.get('sessionId')
        if session_id:
            user_agent = data.get('_user_agent', '')
            session, created = UserSession.objects.get_or_create(
                session_id=session_id,
                defaults={
                    'user': user,
                    'user_agent': user_agent,
                    'ip_address': client_ip,
                    'start_time': timezone.now(),
                },
            )
            session.page_views = session_data.get('pageViews', 0)
            session.feature_usage = session_data.get('featureUsage', {})
            session.user_journey = session_data.get('userJourney', [])

            if session_data.get('duration'):
                session.duration = session_data['duration'] // 1000
                session.end_time = session.start_time + timedelta(seconds=session.duration)

            session.is_engaged = session.duration > 30 or session.page_views > 1
            session.is_bounce = session.page_views <= 1 and session.duration < 30
            session.save()

        # --- Process performance metrics ---
        performance_data = data.get('performance', {})
        if performance_data:
            for metric in performance_data.get('apiResponseTimes', []):
                PerformanceMetric.objects.create(
                    user=user,
                    session_id=session_id,
                    metric_type='api_response',
                    metric_name=metric.get('endpoint', ''),
                    value=metric.get('duration', 0),
                    properties={'status': metric.get('status')},
                    timestamp=timezone.now(),
                )

            for metric in performance_data.get('userFlowTimes', []):
                PerformanceMetric.objects.create(
                    user=user,
                    session_id=session_id,
                    metric_type='user_flow',
                    metric_name=metric.get('flow', ''),
                    value=metric.get('duration', 0),
                    timestamp=timezone.now(),
                )

        logger.info(
            f"Analytics batch processed: {counts['events']} events, "
            f"{counts['engagements']} engagements, {counts['conversions']} conversions"
        )
        return counts

    except Exception as exc:
        logger.error(f"Analytics batch processing failed: {exc}")
        raise self.retry(exc=exc)
