"""
Context Analyzer ML Model
==========================

Real-time context analysis for intent prediction:
- Domain classification
- Login form detection
- Tab switching pattern analysis
- Urgency estimation

@author Password Manager Team
@created 2026-02-06
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


class ContextAnalyzer:
    """
    Analyzes browsing context to improve prediction accuracy
    and trigger predictions at the right moment.
    """
    
    # Domain category patterns
    DOMAIN_PATTERNS = {
        'banking': [
            r'bank', r'chase', r'wellsfargo', r'citi', r'bofa', r'usbank',
            r'capital ?one', r'pnc', r'td ?bank', r'hsbc', r'barclays'
        ],
        'financial': [
            r'paypal', r'venmo', r'zelle', r'cashapp', r'stripe', 
            r'fidelity', r'vanguard', r'schwab', r'etrade', r'robinhood'
        ],
        'social': [
            r'facebook', r'twitter', r'instagram', r'linkedin', r'reddit',
            r'tiktok', r'snapchat', r'pinterest', r'tumblr', r'discord'
        ],
        'work': [
            r'slack', r'teams', r'zoom', r'github', r'gitlab', r'bitbucket',
            r'jira', r'confluence', r'notion', r'asana', r'trello', r'figma',
            r'salesforce', r'hubspot', r'zendesk'
        ],
        'email': [
            r'gmail', r'outlook', r'yahoo', r'proton', r'fastmail',
            r'icloud', r'mail\.'
        ],
        'shopping': [
            r'amazon', r'ebay', r'walmart', r'target', r'bestbuy',
            r'newegg', r'etsy', r'aliexpress', r'shopify'
        ],
        'entertainment': [
            r'netflix', r'hulu', r'disney', r'hbo', r'spotify',
            r'youtube', r'twitch', r'prime ?video', r'peacock'
        ],
        'cloud_storage': [
            r'dropbox', r'drive\.google', r'onedrive', r'box\.com',
            r'icloud', r'mega\.nz'
        ],
        'crypto': [
            r'coinbase', r'binance', r'kraken', r'gemini', r'crypto\.com',
            r'metamask', r'phantom'
        ],
        'healthcare': [
            r'mychart', r'patient', r'health', r'medical', r'pharmacy',
            r'cvs', r'walgreens'
        ]
    }
    
    # Login form indicators
    LOGIN_INDICATORS = {
        'strong': [
            'password', 'passwd', 'pwd', 'pass',
            'login', 'signin', 'sign-in', 'log-in',
            'authenticate', 'auth'
        ],
        'medium': [
            'username', 'userid', 'user', 'email',
            'account', 'credential'
        ],
        'weak': [
            'submit', 'continue', 'next', 'enter'
        ]
    }
    
    def __init__(self):
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        self._domain_regexes = {}
        for category, patterns in self.DOMAIN_PATTERNS.items():
            combined = '|'.join(patterns)
            self._domain_regexes[category] = re.compile(combined, re.IGNORECASE)
    
    def analyze_context(
        self,
        domain: str,
        url_hash: str = None,
        page_title: str = None,
        form_fields: List[str] = None,
        time_on_page: int = 0,
        is_new_tab: bool = False,
        device_type: str = 'desktop',
    ) -> Dict[str, Any]:
        """
        Analyze browsing context and return prediction-relevant signals.
        
        Args:
            domain: Current domain
            url_hash: Hash of full URL
            page_title: Page title
            form_fields: List of detected form field types
            time_on_page: Seconds on current page
            is_new_tab: Whether this is a new tab
            device_type: Device type
            
        Returns:
            Context analysis results
        """
        result = {
            'domain': domain,
            'domain_category': self.classify_domain(domain),
            'login_probability': 0.0,
            'urgency_score': 0.5,
            'should_predict': False,
            'prediction_triggers': [],
        }
        
        # Analyze login form probability
        if form_fields:
            login_prob, triggers = self.detect_login_form(form_fields)
            result['login_probability'] = login_prob
            result['prediction_triggers'].extend(triggers)
        
        # Analyze page title for login indicators
        if page_title:
            title_prob = self.analyze_page_title(page_title)
            result['login_probability'] = max(
                result['login_probability'],
                title_prob
            )
            if title_prob > 0.5:
                result['prediction_triggers'].append('title_indicates_login')
        
        # Calculate urgency based on behavior
        result['urgency_score'] = self.calculate_urgency(
            time_on_page=time_on_page,
            is_new_tab=is_new_tab,
            login_probability=result['login_probability']
        )
        
        # Determine if we should generate predictions
        result['should_predict'] = self._should_trigger_prediction(result)
        
        # Security-sensitive category flag
        result['is_security_sensitive'] = result['domain_category'] in [
            'banking', 'financial', 'healthcare', 'crypto'
        ]
        
        return result
    
    def classify_domain(self, domain: str) -> Optional[str]:
        """
        Classify domain into a category.
        
        Args:
            domain: Domain to classify
            
        Returns:
            Category name or None
        """
        if not domain:
            return None
        
        domain_lower = domain.lower()
        
        for category, regex in self._domain_regexes.items():
            if regex.search(domain_lower):
                return category
        
        return 'other'
    
    def detect_login_form(
        self,
        form_fields: List[str]
    ) -> Tuple[float, List[str]]:
        """
        Detect probability of a login form based on form fields.
        
        Args:
            form_fields: List of form field identifiers/names
            
        Returns:
            Tuple of (probability, trigger reasons)
        """
        if not form_fields:
            return 0.0, []
        
        score = 0.0
        triggers = []
        
        fields_lower = [f.lower() for f in form_fields]
        fields_text = ' '.join(fields_lower)
        
        # Check for strong indicators
        for indicator in self.LOGIN_INDICATORS['strong']:
            if indicator in fields_text:
                score += 0.4
                triggers.append(f'strong_indicator:{indicator}')
        
        # Check for medium indicators
        for indicator in self.LOGIN_INDICATORS['medium']:
            if indicator in fields_text:
                score += 0.2
                triggers.append(f'medium_indicator:{indicator}')
        
        # Check for weak indicators
        for indicator in self.LOGIN_INDICATORS['weak']:
            if indicator in fields_text:
                score += 0.05
        
        # Bonus for password + username/email combo
        has_password = any(
            ind in fields_text 
            for ind in ['password', 'passwd', 'pwd']
        )
        has_username = any(
            ind in fields_text 
            for ind in ['username', 'email', 'user', 'login']
        )
        
        if has_password and has_username:
            score += 0.2
            triggers.append('username_password_combo')
        
        return min(1.0, score), triggers
    
    def analyze_page_title(self, title: str) -> float:
        """
        Analyze page title for login indicators.
        
        Args:
            title: Page title
            
        Returns:
            Login probability based on title
        """
        if not title:
            return 0.0
        
        title_lower = title.lower()
        score = 0.0
        
        # Strong title indicators
        strong_patterns = [
            r'\blogin\b', r'\bsign ?in\b', r'\bsign ?on\b',
            r'\blog ?in\b', r'\bauthenticate\b', r'\bsso\b'
        ]
        
        for pattern in strong_patterns:
            if re.search(pattern, title_lower):
                score += 0.4
        
        # Medium indicators
        medium_patterns = [
            r'\baccount\b', r'\bpassword\b', r'\bcredential',
            r'\baccess\b', r'\benter\b'
        ]
        
        for pattern in medium_patterns:
            if re.search(pattern, title_lower):
                score += 0.15
        
        return min(1.0, score)
    
    def calculate_urgency(
        self,
        time_on_page: int,
        is_new_tab: bool,
        login_probability: float,
    ) -> float:
        """
        Calculate urgency score for prediction timing.
        
        Higher urgency = show predictions sooner.
        
        Args:
            time_on_page: Seconds on page
            is_new_tab: Whether new tab
            login_probability: Login form probability
            
        Returns:
            Urgency score 0-1
        """
        score = 0.5  # Base urgency
        
        # New tab with high login probability = high urgency
        if is_new_tab and login_probability > 0.7:
            score += 0.3
        
        # Short time on page with login form = urgent
        if time_on_page < 5 and login_probability > 0.5:
            score += 0.2
        
        # Long time on page = less urgent (user may be doing something else)
        if time_on_page > 30:
            score -= 0.1
        
        # High login probability increases urgency
        score += login_probability * 0.2
        
        return max(0.0, min(1.0, score))
    
    def _should_trigger_prediction(self, context: Dict[str, Any]) -> bool:
        """Determine if predictions should be generated."""
        
        # High login probability
        if context['login_probability'] >= 0.6:
            return True
        
        # Known category that often needs passwords
        if context['domain_category'] in [
            'banking', 'financial', 'social', 'work', 
            'email', 'shopping', 'crypto'
        ]:
            return True
        
        # High urgency regardless of other factors
        if context['urgency_score'] >= 0.8:
            return True
        
        return False
    
    def extract_page_keywords(self, title: str, limit: int = 5) -> List[str]:
        """
        Extract relevant keywords from page title.
        
        Args:
            title: Page title
            limit: Maximum keywords
            
        Returns:
            List of keywords
        """
        if not title:
            return []
        
        # Remove common noise words
        noise_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at',
            'to', 'for', 'of', 'with', 'by', '-', '|', '–', '—'
        }
        
        # Tokenize and clean
        words = re.findall(r'\b[a-zA-Z]{3,}\b', title.lower())
        keywords = [w for w in words if w not in noise_words]
        
        return keywords[:limit]
    
    def hash_url_for_privacy(self, url: str) -> str:
        """
        Create a privacy-preserving hash of a URL.
        
        Args:
            url: Full URL
            
        Returns:
            SHA-256 hash
        """
        if not url:
            return ''
        
        return hashlib.sha256(url.encode()).hexdigest()


# Singleton instance
_context_analyzer = None


def get_context_analyzer() -> ContextAnalyzer:
    """Get the context analyzer singleton."""
    global _context_analyzer
    if _context_analyzer is None:
        _context_analyzer = ContextAnalyzer()
    return _context_analyzer
