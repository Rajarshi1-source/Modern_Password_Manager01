"""
AI Assistant Views

API endpoints for the conversational security assistant.
All endpoints require authentication.
"""

import logging
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ConversationSession, ChatMessage, AIQueryLog
from .serializers import (
    ConversationSessionListSerializer,
    ConversationSessionDetailSerializer,
    CreateSessionSerializer,
    SendMessageSerializer,
    AIQueryLogSerializer,
)
from .services.claude_service import ClaudeService, ClaudeServiceError
from .services.query_analyzer_service import QueryAnalyzerService

logger = logging.getLogger(__name__)


def _check_feature_enabled():
    """Check if AI Assistant feature is enabled."""
    if not getattr(settings, 'AI_ASSISTANT_ENABLED', True):
        return Response(
            {'error': 'AI Assistant is currently disabled.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    return None


# =============================================================================
# Session Management
# =============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def session_list(request):
    """
    GET: List user's conversation sessions.
    POST: Create a new conversation session.
    """
    disabled = _check_feature_enabled()
    if disabled:
        return disabled
    
    if request.method == 'GET':
        sessions = ConversationSession.objects.filter(
            user=request.user,
            is_active=True
        )
        serializer = ConversationSessionListSerializer(sessions, many=True)
        return Response({
            'status': 'success',
            'count': sessions.count(),
            'sessions': serializer.data
        })
    
    elif request.method == 'POST':
        serializer = CreateSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        session = ConversationSession.objects.create(
            user=request.user,
            title=serializer.validated_data.get('title', 'New Conversation')
        )
        
        return Response({
            'status': 'success',
            'message': 'Conversation session created.',
            'session': ConversationSessionDetailSerializer(session).data
        }, status=status.HTTP_201_CREATED)


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def session_detail(request, session_id):
    """
    GET: Get session with messages.
    DELETE: Soft-delete a session.
    """
    disabled = _check_feature_enabled()
    if disabled:
        return disabled
    
    try:
        session = ConversationSession.objects.get(
            id=session_id,
            user=request.user
        )
    except ConversationSession.DoesNotExist:
        return Response(
            {'error': 'Session not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        serializer = ConversationSessionDetailSerializer(session)
        return Response({
            'status': 'success',
            'session': serializer.data
        })
    
    elif request.method == 'DELETE':
        session.is_active = False
        session.save(update_fields=['is_active'])
        return Response({
            'status': 'success',
            'message': 'Session deleted.'
        })


# =============================================================================
# Chat / Send Message
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_message(request, session_id):
    """
    Send a message in a conversation and get an AI response.
    
    This is the core endpoint that:
    1. Validates the user message
    2. Retrieves conversation history
    3. Builds vault context
    4. Sends to Claude API
    5. Stores both user and assistant messages
    6. Returns the assistant's response
    """
    disabled = _check_feature_enabled()
    if disabled:
        return disabled
    
    # Validate session
    try:
        session = ConversationSession.objects.get(
            id=session_id,
            user=request.user,
            is_active=True
        )
    except ConversationSession.DoesNotExist:
        return Response(
            {'error': 'Session not found or inactive.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Validate message
    serializer = SendMessageSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user_message_content = serializer.validated_data['content']
    
    # Store user message
    user_msg = ChatMessage.objects.create(
        session=session,
        role='user',
        content=user_message_content
    )
    
    try:
        # Get conversation history (last 20 messages for context window)
        history = list(
            session.messages.order_by('timestamp')
            .values('role', 'content')[:20]
        )
        # Remove the just-added user message from history 
        # (it will be passed separately)
        if history and history[-1]['content'] == user_message_content:
            history = history[:-1]
        
        # Build vault context
        query_service = QueryAnalyzerService()
        vault_context = query_service.build_vault_context(
            request.user, session
        )
        
        # Send to Claude
        claude_service = ClaudeService()
        response = claude_service.send_message(
            user=request.user,
            conversation_history=history,
            user_message=user_message_content,
            vault_context=vault_context
        )
        
        # Store assistant response
        assistant_msg = ChatMessage.objects.create(
            session=session,
            role='assistant',
            content=response['content'],
            tokens_used=response['tokens_used'],
            metadata={
                'model': response['model'],
                'input_tokens': response.get('input_tokens', 0),
                'output_tokens': response.get('output_tokens', 0),
            }
        )
        
        # Update session token count
        session.total_tokens_used += response['tokens_used']
        session.save(update_fields=['total_tokens_used'])
        
        # Auto-generate title from first message if still default
        if session.title == 'New Conversation' and session.messages.count() <= 2:
            # Use first 60 chars of user's first message as title
            title = user_message_content[:60]
            if len(user_message_content) > 60:
                title += '...'
            session.title = title
            session.save(update_fields=['title'])
        
        return Response({
            'status': 'success',
            'user_message': {
                'id': str(user_msg.id),
                'role': 'user',
                'content': user_message_content,
                'timestamp': user_msg.timestamp.isoformat(),
            },
            'assistant_message': {
                'id': str(assistant_msg.id),
                'role': 'assistant',
                'content': response['content'],
                'timestamp': assistant_msg.timestamp.isoformat(),
                'tokens_used': response['tokens_used'],
            }
        })
        
    except ClaudeServiceError as e:
        logger.warning(f"Claude service error for user {request.user.username}: {e}")
        
        # Store error as system message
        ChatMessage.objects.create(
            session=session,
            role='system',
            content=f"Error: {str(e)}",
            metadata={'error': True}
        )
        
        return Response({
            'status': 'error',
            'error': str(e),
            'user_message': {
                'id': str(user_msg.id),
                'role': 'user',
                'content': user_message_content,
                'timestamp': user_msg.timestamp.isoformat(),
            }
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    except Exception as e:
        logger.error(f"Unexpected error in AI assistant: {e}", exc_info=True)
        return Response({
            'status': 'error',
            'error': 'An unexpected error occurred. Please try again.',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Proactive Suggestions
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def suggestions(request):
    """
    Get proactive security suggestions based on vault analysis.
    
    Returns actionable insights without requiring a conversation.
    """
    disabled = _check_feature_enabled()
    if disabled:
        return disabled
    
    try:
        query_service = QueryAnalyzerService()
        health = query_service.analyze_password_health(request.user)
        stale = query_service.get_stale_passwords(request.user, days_threshold=365)
        risk = query_service.get_risk_assessment(request.user)
        
        suggestion_list = []
        
        # Health-based suggestions
        if health['health_score'] < 70:
            suggestion_list.append({
                'type': 'warning',
                'icon': '⚠️',
                'title': 'Password Health Needs Attention',
                'description': (
                    f"Your security health score is {health['health_score']}/100. "
                    f"Consider updating your oldest passwords."
                ),
                'action': 'Show me which passwords need updating',
            })
        
        # Stale password suggestions
        if stale['count'] > 0:
            suggestion_list.append({
                'type': 'info',
                'icon': '🕐',
                'title': f"{stale['count']} Passwords Over a Year Old",
                'description': (
                    f"You have {stale['count']} passwords that haven't been "
                    f"changed in over a year."
                ),
                'action': 'Which accounts have the oldest passwords?',
            })
        
        # Risk-based suggestions
        if risk['high_risk_count'] > 0:
            suggestion_list.append({
                'type': 'danger',
                'icon': '🔴',
                'title': f"{risk['high_risk_count']} High-Risk Accounts",
                'description': (
                    f"{risk['high_risk_count']} accounts have been identified "
                    f"as high risk based on password age and activity."
                ),
                'action': 'Which of my accounts are most at risk?',
            })
        
        # Positive reinforcement
        if health['health_score'] >= 90:
            suggestion_list.append({
                'type': 'success',
                'icon': '✅',
                'title': 'Excellent Security Posture!',
                'description': (
                    f"Your health score is {health['health_score']}/100. "
                    f"Keep up the great work!"
                ),
                'action': 'How can I maintain this score?',
            })
        
        # If no specific suggestions, add a general one
        if not suggestion_list:
            suggestion_list.append({
                'type': 'info',
                'icon': '💡',
                'title': 'Ask Me Anything',
                'description': 'Ask about your password security, breach status, or best practices.',
                'action': 'Give me a security overview',
            })
        
        return Response({
            'status': 'success',
            'suggestions': suggestion_list,
            'health_score': health['health_score'],
            'total_passwords': health['total_passwords'],
        })
        
    except Exception as e:
        logger.error(f"Error generating suggestions: {e}", exc_info=True)
        return Response({
            'status': 'error',
            'error': 'Unable to generate suggestions.',
            'suggestions': []
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Query Audit Log
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def query_log(request):
    """
    View AI query audit trail.
    
    Shows what vault data the AI has accessed during conversations.
    """
    disabled = _check_feature_enabled()
    if disabled:
        return disabled
    
    logs = AIQueryLog.objects.filter(user=request.user)[:50]
    serializer = AIQueryLogSerializer(logs, many=True)
    
    return Response({
        'status': 'success',
        'count': len(serializer.data),
        'logs': serializer.data
    })
