"""
AI Assistant Admin Configuration

Registers AI assistant models in the Django admin panel.
"""

from django.contrib import admin
from .models import ConversationSession, ChatMessage, AIQueryLog


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ['id', 'role', 'content', 'timestamp', 'tokens_used']
    ordering = ['timestamp']


@admin.register(ConversationSession)
class ConversationSessionAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'user', 'started_at', 'last_activity',
        'is_active', 'total_tokens_used', 'message_count_display'
    ]
    list_filter = ['is_active', 'started_at']
    search_fields = ['title', 'user__username']
    readonly_fields = ['id', 'started_at', 'last_activity', 'total_tokens_used']
    inlines = [ChatMessageInline]
    
    def message_count_display(self, obj):
        return obj.messages.count()
    message_count_display.short_description = 'Messages'


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = [
        'short_content', 'role', 'session', 'timestamp', 'tokens_used'
    ]
    list_filter = ['role', 'timestamp']
    search_fields = ['content']
    readonly_fields = ['id', 'timestamp']
    
    def short_content(self, obj):
        return obj.content[:80] + '...' if len(obj.content) > 80 else obj.content
    short_content.short_description = 'Content'


@admin.register(AIQueryLog)
class AIQueryLogAdmin(admin.ModelAdmin):
    list_display = [
        'query_type', 'user', 'query_summary',
        'vault_items_accessed_count', 'timestamp'
    ]
    list_filter = ['query_type', 'timestamp']
    search_fields = ['query_summary', 'user__username']
    readonly_fields = ['id', 'timestamp']
