"""
AI Assistant Serializers

DRF serializers for conversation sessions, messages, and query logs.
"""

from rest_framework import serializers
from .models import ConversationSession, ChatMessage, AIQueryLog


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for individual chat messages."""
    
    class Meta:
        model = ChatMessage
        fields = [
            'id', 'role', 'content', 'timestamp',
            'tokens_used', 'metadata'
        ]
        read_only_fields = ['id', 'timestamp', 'tokens_used', 'metadata']


class ConversationSessionListSerializer(serializers.ModelSerializer):
    """Serializer for listing conversation sessions (summary view)."""
    
    message_count = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = ConversationSession
        fields = [
            'id', 'title', 'started_at', 'last_activity',
            'is_active', 'message_count', 'last_message_preview',
            'total_tokens_used'
        ]
        read_only_fields = [
            'id', 'started_at', 'last_activity',
            'total_tokens_used'
        ]
    
    def get_message_count(self, obj):
        return obj.messages.count()
    
    def get_last_message_preview(self, obj):
        last_msg = obj.messages.order_by('-timestamp').first()
        if last_msg:
            preview = last_msg.content[:100]
            if len(last_msg.content) > 100:
                preview += '...'
            return {
                'role': last_msg.role,
                'content': preview,
                'timestamp': last_msg.timestamp.isoformat()
            }
        return None


class ConversationSessionDetailSerializer(serializers.ModelSerializer):
    """Serializer for conversation session detail (with messages)."""
    
    messages = ChatMessageSerializer(many=True, read_only=True)
    message_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ConversationSession
        fields = [
            'id', 'title', 'started_at', 'last_activity',
            'is_active', 'context_metadata', 'total_tokens_used',
            'message_count', 'messages'
        ]
        read_only_fields = [
            'id', 'started_at', 'last_activity',
            'total_tokens_used', 'messages'
        ]
    
    def get_message_count(self, obj):
        return obj.messages.count()


class CreateSessionSerializer(serializers.Serializer):
    """Serializer for creating a new conversation session."""
    
    title = serializers.CharField(
        max_length=255,
        required=False,
        default='New Conversation'
    )


class SendMessageSerializer(serializers.Serializer):
    """Serializer for sending a message to the AI assistant."""
    
    content = serializers.CharField(
        max_length=10000,
        help_text="The user's message to the AI assistant"
    )
    
    def validate_content(self, value):
        """Validate message content."""
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Message content cannot be empty.")
        if len(value) < 2:
            raise serializers.ValidationError(
                "Message must be at least 2 characters long."
            )
        return value


class AIQueryLogSerializer(serializers.ModelSerializer):
    """Serializer for AI query audit logs."""
    
    class Meta:
        model = AIQueryLog
        fields = [
            'id', 'session', 'query_type', 'query_summary',
            'vault_items_accessed_count', 'timestamp'
        ]
        read_only_fields = ['id', 'session', 'query_type', 'query_summary',
                            'vault_items_accessed_count', 'timestamp']
