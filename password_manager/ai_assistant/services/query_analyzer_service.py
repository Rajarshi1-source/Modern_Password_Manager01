"""
Query Analyzer Service

Read-only vault data access layer for AI assistant queries.
Provides aggregated security insights without ever exposing
plaintext passwords or sensitive credentials.
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q, F
from django.core.cache import cache

from ai_assistant.models import AIQueryLog

logger = logging.getLogger(__name__)


class QueryAnalyzerService:
    """
    Analyzes vault and security data to provide context for AI responses.
    
    SECURITY: This service NEVER returns decrypted passwords.
    Only metadata (domain, age, strength score, tags, timestamps) is accessed.
    All queries are logged to AIQueryLog for audit compliance.
    """
    
    def _get_vault_items(self, user):
        """Get active (non-deleted) vault items for a user."""
        from vault.models import EncryptedVaultItem
        return EncryptedVaultItem.objects.filter(
            user=user,
            deleted=False
        )
    
    def _log_query(self, user, session, query_type, summary, items_count=0):
        """Create an audit log entry for a vault data query."""
        try:
            AIQueryLog.objects.create(
                user=user,
                session=session,
                query_type=query_type,
                query_summary=summary,
                vault_items_accessed_count=items_count,
            )
        except Exception as e:
            logger.error(f"Failed to log AI query: {e}")
    
    def analyze_password_health(self, user, session=None):
        """
        Get aggregated password health statistics.
        
        Returns:
            dict with counts of total, weak, reused, old passwords
            and an overall health score.
        """
        items = self._get_vault_items(user).filter(item_type='password')
        total_count = items.count()
        
        if total_count == 0:
            self._log_query(
                user, session, 'password_health',
                'Analyzed password health - no passwords found', 0
            )
            return {
                'total_passwords': 0,
                'health_score': 100,
                'weak_count': 0,
                'old_count': 0,
                'recently_updated_count': 0,
                'favorite_count': 0,
                'summary': 'No passwords stored in the vault yet.'
            }
        
        # Passwords older than 1 year
        one_year_ago = timezone.now() - timedelta(days=365)
        old_count = items.filter(updated_at__lt=one_year_ago).count()
        
        # Passwords older than 90 days (stale)
        ninety_days_ago = timezone.now() - timedelta(days=90)
        stale_count = items.filter(updated_at__lt=ninety_days_ago).count()
        
        # Recently updated (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_count = items.filter(updated_at__gte=thirty_days_ago).count()
        
        # Favorites
        favorite_count = items.filter(favorite=True).count()
        
        # Calculate health score (simple heuristic)
        old_penalty = min(50, (old_count / total_count) * 50) if total_count > 0 else 0
        stale_penalty = min(30, (stale_count / total_count) * 30) if total_count > 0 else 0
        health_score = max(0, int(100 - old_penalty - stale_penalty))
        
        self._log_query(
            user, session, 'password_health',
            f'Analyzed password health: {total_count} passwords, '
            f'{old_count} old, score={health_score}',
            total_count
        )
        
        return {
            'total_passwords': total_count,
            'health_score': health_score,
            'old_count': old_count,
            'stale_count': stale_count,
            'recently_updated_count': recent_count,
            'favorite_count': favorite_count,
            'summary': (
                f"You have {total_count} passwords. "
                f"{old_count} haven't been changed in over a year. "
                f"{recent_count} were updated in the last 30 days. "
                f"Overall health score: {health_score}/100."
            )
        }
    
    def get_stale_passwords(self, user, days_threshold=365, session=None):
        """
        Get passwords that haven't been changed in X days.
        
        Returns metadata only (domain/service, age in days, tags).
        NEVER returns the actual password.
        """
        threshold_date = timezone.now() - timedelta(days=days_threshold)
        items = self._get_vault_items(user).filter(
            item_type='password',
            updated_at__lt=threshold_date
        ).order_by('updated_at')
        
        stale_list = []
        for item in items[:50]:  # Cap at 50 results
            days_old = (timezone.now() - item.updated_at).days
            stale_list.append({
                'item_id': str(item.item_id)[:8] + '...',
                'item_type': item.item_type,
                'tags': item.tags if item.tags else [],
                'last_updated': item.updated_at.isoformat(),
                'days_since_update': days_old,
                'is_favorite': item.favorite,
            })
        
        self._log_query(
            user, session, 'age_analysis',
            f'Retrieved {len(stale_list)} passwords older than {days_threshold} days',
            len(stale_list)
        )
        
        return {
            'threshold_days': days_threshold,
            'count': len(stale_list),
            'passwords': stale_list,
            'summary': (
                f"Found {len(stale_list)} passwords that haven't been updated "
                f"in over {days_threshold} days."
            )
        }
    
    def get_risk_assessment(self, user, session=None):
        """
        Generate a per-account risk assessment based on available metadata.
        
        Risk factors:
        - Password age (older = higher risk)
        - No tags (could indicate forgotten/orphaned accounts)
        - Not marked as favorite (less likely to be monitored)
        """
        items = self._get_vault_items(user).filter(item_type='password')
        total = items.count()
        
        if total == 0:
            self._log_query(
                user, session, 'risk_assessment',
                'Risk assessment - no passwords found', 0
            )
            return {
                'total_assessed': 0,
                'high_risk_count': 0,
                'medium_risk_count': 0,
                'low_risk_count': 0,
                'summary': 'No passwords to assess.'
            }
        
        high_risk = 0
        medium_risk = 0
        low_risk = 0
        high_risk_items = []
        
        one_year_ago = timezone.now() - timedelta(days=365)
        six_months_ago = timezone.now() - timedelta(days=180)
        
        for item in items:
            risk_score = 0
            risk_factors = []
            
            # Age-based risk
            if item.updated_at < one_year_ago:
                risk_score += 40
                risk_factors.append('Password over 1 year old')
            elif item.updated_at < six_months_ago:
                risk_score += 20
                risk_factors.append('Password over 6 months old')
            
            # No tags = potentially forgotten
            if not item.tags:
                risk_score += 15
                risk_factors.append('No tags/labels assigned')
            
            # Never used
            if not item.last_used_at:
                risk_score += 10
                risk_factors.append('Never accessed through vault')
            
            # Classify
            if risk_score >= 40:
                high_risk += 1
                if len(high_risk_items) < 10:
                    high_risk_items.append({
                        'item_id': str(item.item_id)[:8] + '...',
                        'risk_score': risk_score,
                        'risk_factors': risk_factors,
                        'days_since_update': (timezone.now() - item.updated_at).days,
                    })
            elif risk_score >= 20:
                medium_risk += 1
            else:
                low_risk += 1
        
        self._log_query(
            user, session, 'risk_assessment',
            f'Risk assessment: {high_risk} high, {medium_risk} medium, {low_risk} low risk',
            total
        )
        
        return {
            'total_assessed': total,
            'high_risk_count': high_risk,
            'medium_risk_count': medium_risk,
            'low_risk_count': low_risk,
            'high_risk_items': high_risk_items,
            'summary': (
                f"Assessed {total} passwords: "
                f"{high_risk} high risk, {medium_risk} medium risk, {low_risk} low risk. "
                f"{'Consider updating your high-risk passwords first.' if high_risk > 0 else 'Looking good!'}"
            )
        }
    
    def search_vault_metadata(self, user, query, session=None):
        """
        Search vault items by metadata (tags, dates, type).
        
        NEVER exposes encrypted data or passwords.
        Only searches through tags and item metadata.
        """
        items = self._get_vault_items(user)
        
        # Search by tags (case-insensitive)
        # Tags are stored as JSON arrays
        matching_items = []
        query_lower = query.lower()
        
        for item in items:
            matched = False
            match_reasons = []
            
            # Check tags
            if item.tags:
                for tag in item.tags:
                    if query_lower in str(tag).lower():
                        matched = True
                        match_reasons.append(f'Tag: {tag}')
            
            # Check item type
            if query_lower in item.item_type.lower():
                matched = True
                match_reasons.append(f'Type: {item.item_type}')
            
            if matched:
                matching_items.append({
                    'item_id': str(item.item_id)[:8] + '...',
                    'item_type': item.item_type,
                    'tags': item.tags if item.tags else [],
                    'match_reasons': match_reasons,
                    'created_at': item.created_at.isoformat(),
                    'updated_at': item.updated_at.isoformat(),
                    'is_favorite': item.favorite,
                })
            
            if len(matching_items) >= 20:  # Cap results
                break
        
        self._log_query(
            user, session, 'vault_search',
            f'Searched vault for "{query}", found {len(matching_items)} matches',
            len(matching_items)
        )
        
        return {
            'query': query,
            'count': len(matching_items),
            'results': matching_items,
            'summary': (
                f"Found {len(matching_items)} items matching '{query}'."
                if matching_items else
                f"No items found matching '{query}'."
            )
        }
    
    def get_security_summary(self, user, session=None):
        """
        Get an overall security posture summary for the user.
        
        Combines password health, risk assessment, and account statistics.
        Results are cached for 2 minutes to avoid 5-8 DB queries per chat message.
        """
        # Check cache first — avoids repeated DB queries during chat sessions
        cache_key = f'ai_security_summary:{user.id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        
        health = self.analyze_password_health(user, session)
        items = self._get_vault_items(user)
        
        # Item type breakdown
        type_counts = dict(
            items.values('item_type').annotate(count=Count('id')).values_list('item_type', 'count')
        )
        
        # Activity metrics
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_activity = items.filter(updated_at__gte=thirty_days_ago).count()
        
        # Folder usage
        items_in_folders = items.filter(folder__isnull=False).count()
        total_items = items.count()
        
        self._log_query(
            user, session, 'security_summary',
            f'Generated security summary: {total_items} total items',
            total_items
        )
        
        result = {
            'total_items': total_items,
            'item_type_breakdown': type_counts,
            'health_score': health['health_score'],
            'passwords_over_year_old': health.get('old_count', 0),
            'recently_updated': recent_activity,
            'items_in_folders': items_in_folders,
            'organization_score': (
                int((items_in_folders / total_items) * 100) if total_items > 0 else 100
            ),
            'summary': (
                f"Your vault has {total_items} items "
                f"({type_counts.get('password', 0)} passwords, "
                f"{type_counts.get('card', 0)} cards, "
                f"{type_counts.get('note', 0)} notes, "
                f"{type_counts.get('identity', 0)} identities). "
                f"Health score: {health['health_score']}/100. "
                f"{recent_activity} items updated in the last 30 days."
            )
        }
        
        # Cache for 2 minutes to avoid repeated queries during chat sessions
        cache.set(cache_key, result, 120)
        
        return result
    
    def build_vault_context(self, user, session=None):
        """
        Build a vault context string for the AI system prompt.
        
        This gives the AI high-level awareness of the user's vault
        without exposing any sensitive data.
        """
        try:
            summary = self.get_security_summary(user, session)
            
            context = f"""The user has {summary['total_items']} items in their vault:
- {summary['item_type_breakdown'].get('password', 0)} passwords
- {summary['item_type_breakdown'].get('card', 0)} payment cards
- {summary['item_type_breakdown'].get('note', 0)} secure notes
- {summary['item_type_breakdown'].get('identity', 0)} identities

Security health score: {summary['health_score']}/100
Passwords over 1 year old: {summary['passwords_over_year_old']}
Items updated in last 30 days: {summary['recently_updated']}
Organization score: {summary['organization_score']}%"""
            
            return context
        except Exception as e:
            logger.error(f"Failed to build vault context: {e}")
            return "Vault context unavailable."


def get_query_analyzer_service():
    """Factory function to get a QueryAnalyzerService instance."""
    return QueryAnalyzerService()
