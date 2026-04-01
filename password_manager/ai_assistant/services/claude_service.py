"""
Claude API Integration Service

Handles all communication with the Anthropic Claude API for the
conversational security assistant. Includes rate limiting, retry logic,
and response sanitization.
"""

import logging
import time
import re
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class ClaudeServiceError(Exception):
    """Custom exception for Claude service errors."""
    pass


class ClaudeService:
    """
    Service for interacting with the Claude API.
    
    Handles:
    - Building security-focused system prompts
    - Sending messages with conversation history
    - Rate limiting per user
    - Response sanitization
    - Error handling with retry logic
    """
    
    # Rate limit: requests per user per hour
    RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds
    
    def __init__(self):
        self.api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
        self.model = getattr(settings, 'AI_ASSISTANT_MODEL', 'claude-sonnet-4-20250514')
        self.max_tokens = getattr(settings, 'AI_ASSISTANT_MAX_TOKENS', 4096)
        self.rate_limit = self._parse_rate_limit(
            getattr(settings, 'AI_ASSISTANT_RATE_LIMIT', '20/hour')
        )
        self._client = None
    
    def _parse_rate_limit(self, rate_str):
        """Parse rate limit string like '20/hour' to integer."""
        try:
            return int(rate_str.split('/')[0])
        except (ValueError, IndexError):
            return 20
    
    @property
    def client(self):
        """Lazy-initialize the Anthropic client."""
        if self._client is None:
            if not self.api_key:
                raise ClaudeServiceError(
                    "ANTHROPIC_API_KEY is not configured. "
                    "Please set it in your environment variables."
                )
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ClaudeServiceError(
                    "The 'anthropic' package is not installed. "
                    "Run: pip install anthropic"
                )
        return self._client
    
    def _check_rate_limit(self, user_id):
        """
        Check and enforce per-user rate limiting.
        
        Uses Django cache with atomic operations to track request counts.
        """
        cache_key = f"ai_assistant_rate_{user_id}"
        
        # cache.add() is atomic: sets only if key doesn't exist
        if cache.add(cache_key, 1, self.RATE_LIMIT_WINDOW):
            # Key was newly created with value 1 — first request in window
            return
        
        # Key already exists — atomically increment and check
        try:
            current_count = cache.incr(cache_key)
        except ValueError:
            # Key expired between add() and incr() — reset
            cache.set(cache_key, 1, self.RATE_LIMIT_WINDOW)
            return
        
        if current_count > self.rate_limit:
            raise ClaudeServiceError(
                f"Rate limit exceeded. Maximum {self.rate_limit} requests per hour. "
                "Please try again later."
            )
    
    def _build_system_prompt(self, user, vault_context=None):
        """
        Build a security-focused system prompt for Claude.
        
        The system prompt instructs Claude on its role, capabilities,
        and strict data handling rules.
        """
        system_prompt = f"""You are a security assistant integrated into a password manager application called "Vault". You help the user "{user.username}" understand and improve their password security.

## Your Capabilities
- Analyze password health metrics (weak, reused, old passwords)
- Explain security concepts in simple, accessible language
- Recommend security improvements
- Answer questions about the password manager's features
- Assess account risk levels
- Help users understand breach notifications

## Important Rules
1. **NEVER generate, suggest, or display actual passwords.** Only discuss password characteristics (length, complexity, age).
2. **NEVER reveal raw password data.** Only reference metadata like domain names, creation dates, and strength scores.
3. **Be concise and actionable.** Users want clear next steps, not lectures.
4. **Use markdown formatting** for readability (bullets, bold, headers).
5. **If unsure, say so.** Don't fabricate security information.
6. **Prioritize user safety.** If something seems like a phishing attempt or social engineering, warn the user.
7. **Refer to account items by their domain/service name**, never by passwords or sensitive credentials.

## Tone
Be friendly, professional, and reassuring. Security can be intimidating — make it approachable. Use analogies when explaining complex concepts."""

        # Add vault context if available
        if vault_context:
            system_prompt += f"""

## Current Vault Context
{vault_context}"""
        
        return system_prompt
    
    def _sanitize_response(self, response_text):
        """
        Sanitize Claude's response to remove any potentially leaked sensitive data.
        
        Strips patterns that look like passwords, API keys, or credentials.
        """
        # Remove anything that looks like a raw password or secret
        # Pattern: strings that look like they could be passwords (mixed case, numbers, symbols)
        sanitized = re.sub(
            r'(?:password|secret|key|token|credential)\s*[:=]\s*["\']?[\w!@#$%^&*()\-+=]{8,}["\']?',
            '[REDACTED]',
            response_text,
            flags=re.IGNORECASE
        )
        
        # Remove potential API keys
        sanitized = re.sub(
            r'(?:sk-|pk-|api[_-]?key[_-]?)[\w\-]{20,}',
            '[REDACTED_KEY]',
            sanitized,
            flags=re.IGNORECASE
        )
        
        return sanitized
    
    def send_message(self, user, conversation_history, user_message, vault_context=None):
        """
        Send a message to Claude and get a response.
        
        Args:
            user: Django User object
            conversation_history: List of dicts with 'role' and 'content' keys
            user_message: The new user message string
            vault_context: Optional string with vault data context
            
        Returns:
            dict with:
                - content: The assistant's response text
                - tokens_used: Total tokens consumed
                - model: Model used
        """
        # Check feature flag
        if not getattr(settings, 'AI_ASSISTANT_ENABLED', True):
            raise ClaudeServiceError("AI Assistant is currently disabled.")
        
        # Enforce rate limit
        self._check_rate_limit(user.id)
        
        # Build system prompt
        system_prompt = self._build_system_prompt(user, vault_context)
        
        # Build messages list
        messages = []
        for msg in conversation_history:
            if msg['role'] in ('user', 'assistant'):
                messages.append({
                    'role': msg['role'],
                    'content': msg['content']
                })
        
        # Add the new user message
        messages.append({
            'role': 'user',
            'content': user_message
        })
        
        # Call Claude API with retry logic
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=system_prompt,
                    messages=messages
                )
                
                # Extract response
                response_text = response.content[0].text
                
                # Sanitize response
                sanitized_text = self._sanitize_response(response_text)
                
                # Calculate tokens
                tokens_used = (response.usage.input_tokens + response.usage.output_tokens)
                
                return {
                    'content': sanitized_text,
                    'tokens_used': tokens_used,
                    'model': self.model,
                    'input_tokens': response.usage.input_tokens,
                    'output_tokens': response.usage.output_tokens,
                }
                
            except ClaudeServiceError:
                raise
            except Exception as e:
                logger.warning(
                    f"Claude API attempt {attempt + 1}/{max_retries} failed: {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    logger.error(f"Claude API failed after {max_retries} attempts: {e}")
                    raise ClaudeServiceError(
                        "Unable to get a response from the AI assistant. "
                        "Please try again in a moment."
                    )


def get_claude_service():
    """Factory function to get a ClaudeService instance."""
    return ClaudeService()
