"""
AI Assistant Models

Models for conversational AI security assistant sessions, messages, and audit logs.
"""

import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ConversationSession(models.Model):
    """
    Groups messages into a conversation thread.
    
    Each user can have multiple sessions (chat threads).
    Sessions maintain context for multi-turn conversations.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ai_sessions'
    )
    title = models.CharField(
        max_length=255,
        default='New Conversation',
        help_text="Auto-generated or user-defined conversation title"
    )
    started_at = models.DateTimeField(default=timezone.now)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    # Contextual metadata for the conversation
    context_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Conversation context: topics discussed, vault items referenced, etc."
    )
    
    # Total tokens used across all messages in this session
    total_tokens_used = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['user', '-last_activity']),
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"AI Session: {self.title[:40]} ({self.user.username})"
    
    def message_count(self):
        """Return total number of messages in this session."""
        return self.messages.count()


class ChatMessage(models.Model):
    """
    Individual message in a conversation session.
    
    Messages can be from the user, the AI assistant, or system prompts.
    """
    
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        ConversationSession,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    
    # Token usage tracking
    tokens_used = models.IntegerField(
        default=0,
        help_text="Tokens consumed for this message (input + output for assistant)"
    )
    
    # Message metadata (e.g., error info, query types triggered)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata: queries triggered, processing time, etc."
    )
    
    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['session', 'timestamp']),
            models.Index(fields=['role']),
        ]
    
    def __str__(self):
        preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f"[{self.role}] {preview}"


class AIQueryLog(models.Model):
    """
    Audit log for vault-data queries made by the AI assistant.
    
    Tracks what data the AI accessed to ensure transparency
    and compliance with security policies.
    """
    
    QUERY_TYPE_CHOICES = [
        ('password_health', 'Password Health Analysis'),
        ('breach_check', 'Breach Check'),
        ('age_analysis', 'Password Age Analysis'),
        ('risk_assessment', 'Risk Assessment'),
        ('vault_search', 'Vault Metadata Search'),
        ('security_summary', 'Security Summary'),
        ('general', 'General Security Query'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        ConversationSession,
        on_delete=models.CASCADE,
        related_name='query_logs',
        null=True,
        blank=True
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ai_query_logs'
    )
    query_type = models.CharField(max_length=30, choices=QUERY_TYPE_CHOICES)
    query_summary = models.TextField(
        help_text="Description of what data was queried"
    )
    vault_items_accessed_count = models.IntegerField(
        default=0,
        help_text="Number of vault items accessed (metadata only)"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['query_type']),
        ]
    
    def __str__(self):
        return f"AI Query [{self.query_type}] by {self.user.username} @ {self.timestamp}"
