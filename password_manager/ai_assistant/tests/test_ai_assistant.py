"""
Test suite for AI-Powered Security Assistant

Tests the AI assistant models, services, API endpoints, and integration.
All Claude API calls are mocked to avoid external dependencies.
"""

import uuid
from unittest.mock import patch, MagicMock, PropertyMock
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from ai_assistant.models import (
    ConversationSession,
    ChatMessage,
    AIQueryLog,
)
from ai_assistant.services.claude_service import ClaudeService, ClaudeServiceError
from ai_assistant.services.query_analyzer_service import QueryAnalyzerService


# =============================================================================
# Model Tests
# =============================================================================

class ConversationSessionModelTests(TestCase):
    """Tests for ConversationSession model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_session(self):
        """Test creating a conversation session."""
        session = ConversationSession.objects.create(
            user=self.user,
            title='Test Conversation'
        )
        
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.title, 'Test Conversation')
        self.assertTrue(session.is_active)
        self.assertEqual(session.total_tokens_used, 0)
    
    def test_session_str(self):
        """Test string representation."""
        session = ConversationSession.objects.create(
            user=self.user,
            title='My Security Chat'
        )
        self.assertIn('My Security Chat', str(session))
        self.assertIn(self.user.username, str(session))
    
    def test_session_default_title(self):
        """Test default title is set."""
        session = ConversationSession.objects.create(user=self.user)
        self.assertEqual(session.title, 'New Conversation')
    
    def test_message_count(self):
        """Test message count method."""
        session = ConversationSession.objects.create(user=self.user)
        self.assertEqual(session.message_count(), 0)
        
        ChatMessage.objects.create(
            session=session,
            role='user',
            content='Hello'
        )
        self.assertEqual(session.message_count(), 1)
    
    def test_session_ordering(self):
        """Test sessions are ordered by last_activity descending."""
        session1 = ConversationSession.objects.create(
            user=self.user,
            title='First'
        )
        session2 = ConversationSession.objects.create(
            user=self.user,
            title='Second'
        )
        
        sessions = list(ConversationSession.objects.filter(user=self.user))
        self.assertEqual(sessions[0], session2)  # Most recent first
    
    def test_context_metadata_default(self):
        """Test context_metadata defaults to empty dict."""
        session = ConversationSession.objects.create(user=self.user)
        self.assertEqual(session.context_metadata, {})


class ChatMessageModelTests(TestCase):
    """Tests for ChatMessage model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.session = ConversationSession.objects.create(
            user=self.user,
            title='Test Session'
        )
    
    def test_create_user_message(self):
        """Test creating a user message."""
        msg = ChatMessage.objects.create(
            session=self.session,
            role='user',
            content='Why is my password weak?'
        )
        
        self.assertEqual(msg.role, 'user')
        self.assertEqual(msg.content, 'Why is my password weak?')
        self.assertEqual(msg.tokens_used, 0)
    
    def test_create_assistant_message(self):
        """Test creating an assistant message."""
        msg = ChatMessage.objects.create(
            session=self.session,
            role='assistant',
            content='Your password is weak because...',
            tokens_used=150,
            metadata={'model': 'claude-sonnet-4-20250514'}
        )
        
        self.assertEqual(msg.role, 'assistant')
        self.assertEqual(msg.tokens_used, 150)
        self.assertEqual(msg.metadata['model'], 'claude-sonnet-4-20250514')
    
    def test_message_str(self):
        """Test string representation."""
        msg = ChatMessage.objects.create(
            session=self.session,
            role='user',
            content='Hello world'
        )
        self.assertIn('[user]', str(msg))
        self.assertIn('Hello world', str(msg))
    
    def test_message_str_truncation(self):
        """Test long messages are truncated in str."""
        long_content = 'A' * 100
        msg = ChatMessage.objects.create(
            session=self.session,
            role='assistant',
            content=long_content
        )
        self.assertIn('...', str(msg))
    
    def test_message_ordering(self):
        """Test messages are ordered by timestamp ascending."""
        msg1 = ChatMessage.objects.create(
            session=self.session,
            role='user',
            content='First'
        )
        msg2 = ChatMessage.objects.create(
            session=self.session,
            role='assistant',
            content='Second'
        )
        
        messages = list(self.session.messages.all())
        self.assertEqual(messages[0], msg1)
        self.assertEqual(messages[1], msg2)
    
    def test_system_message(self):
        """Test creating a system message."""
        msg = ChatMessage.objects.create(
            session=self.session,
            role='system',
            content='Error: Rate limit exceeded',
            metadata={'error': True}
        )
        self.assertEqual(msg.role, 'system')
        self.assertTrue(msg.metadata.get('error'))


class AIQueryLogModelTests(TestCase):
    """Tests for AIQueryLog model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.session = ConversationSession.objects.create(
            user=self.user
        )
    
    def test_create_query_log(self):
        """Test creating a query log entry."""
        log = AIQueryLog.objects.create(
            user=self.user,
            session=self.session,
            query_type='password_health',
            query_summary='Analyzed password health stats',
            vault_items_accessed_count=15
        )
        
        self.assertEqual(log.query_type, 'password_health')
        self.assertEqual(log.vault_items_accessed_count, 15)
    
    def test_query_log_without_session(self):
        """Test creating a query log without a session."""
        log = AIQueryLog.objects.create(
            user=self.user,
            query_type='security_summary',
            query_summary='Generated security summary',
        )
        self.assertIsNone(log.session)
    
    def test_query_log_str(self):
        """Test string representation."""
        log = AIQueryLog.objects.create(
            user=self.user,
            query_type='risk_assessment',
            query_summary='Risk assessment performed',
        )
        self.assertIn('risk_assessment', str(log))
        self.assertIn(self.user.username, str(log))
    
    def test_query_log_ordering(self):
        """Test logs are ordered by timestamp descending."""
        log1 = AIQueryLog.objects.create(
            user=self.user,
            query_type='password_health',
            query_summary='First query',
        )
        log2 = AIQueryLog.objects.create(
            user=self.user,
            query_type='breach_check',
            query_summary='Second query',
        )
        
        logs = list(AIQueryLog.objects.filter(user=self.user))
        self.assertEqual(logs[0], log2)


# =============================================================================
# Service Tests
# =============================================================================

class ClaudeServiceTests(TestCase):
    """Tests for ClaudeService with mocked Claude API."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    @override_settings(
        ANTHROPIC_API_KEY='test-key',
        AI_ASSISTANT_MODEL='claude-sonnet-4-20250514',
        AI_ASSISTANT_MAX_TOKENS=4096,
        AI_ASSISTANT_RATE_LIMIT='20/hour',
        AI_ASSISTANT_ENABLED=True
    )
    @patch('ai_assistant.services.claude_service.ClaudeService.client', new_callable=PropertyMock)
    def test_send_message_success(self, mock_client_prop):
        """Test successful message sending."""
        # Mock the Anthropic client response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='Your password is strong because it has 16 characters.')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_client_prop.return_value = mock_client
        
        service = ClaudeService()
        result = service.send_message(
            user=self.user,
            conversation_history=[],
            user_message='Is my password strong?'
        )
        
        self.assertIn('content', result)
        self.assertEqual(result['tokens_used'], 150)
        self.assertIn('model', result)
    
    @override_settings(
        ANTHROPIC_API_KEY='',
        AI_ASSISTANT_ENABLED=True
    )
    def test_missing_api_key(self):
        """Test error when API key is missing."""
        service = ClaudeService()
        with self.assertRaises(ClaudeServiceError):
            service.send_message(
                user=self.user,
                conversation_history=[],
                user_message='Hello'
            )
    
    @override_settings(
        AI_ASSISTANT_ENABLED=False
    )
    def test_feature_disabled(self):
        """Test error when AI assistant is disabled."""
        service = ClaudeService()
        with self.assertRaises(ClaudeServiceError):
            service.send_message(
                user=self.user,
                conversation_history=[],
                user_message='Hello'
            )
    
    @override_settings(
        ANTHROPIC_API_KEY='test-key',
        AI_ASSISTANT_RATE_LIMIT='2/hour',
        AI_ASSISTANT_ENABLED=True
    )
    @patch('ai_assistant.services.claude_service.ClaudeService.client', new_callable=PropertyMock)
    @patch('ai_assistant.services.claude_service.cache')
    def test_rate_limiting(self, mock_cache, mock_client_prop):
        """Test rate limiting enforcement."""
        # Simulate rate limit exceeded
        mock_cache.get.return_value = 5  # Already at 5, limit is 2
        
        service = ClaudeService()
        with self.assertRaises(ClaudeServiceError) as ctx:
            service.send_message(
                user=self.user,
                conversation_history=[],
                user_message='Hello'
            )
        self.assertIn('Rate limit', str(ctx.exception))
    
    def test_sanitize_response(self):
        """Test response sanitization removes sensitive data."""
        service = ClaudeService()
        
        # Test password pattern removal
        response = "Your password: MyS3cret!Pass should be changed"
        sanitized = service._sanitize_response(response)
        self.assertNotIn('MyS3cret!Pass', sanitized)
    
    def test_build_system_prompt(self):
        """Test system prompt construction."""
        service = ClaudeService()
        prompt = service._build_system_prompt(self.user)
        
        self.assertIn(self.user.username, prompt)
        self.assertIn('NEVER', prompt)
        self.assertIn('password', prompt.lower())
    
    def test_build_system_prompt_with_context(self):
        """Test system prompt includes vault context when provided."""
        service = ClaudeService()
        context = "User has 50 passwords, health score: 75/100"
        prompt = service._build_system_prompt(self.user, vault_context=context)
        
        self.assertIn('50 passwords', prompt)
        self.assertIn('75/100', prompt)
    
    def test_parse_rate_limit(self):
        """Test rate limit string parsing."""
        service = ClaudeService()
        self.assertEqual(service._parse_rate_limit('20/hour'), 20)
        self.assertEqual(service._parse_rate_limit('100/minute'), 100)
        self.assertEqual(service._parse_rate_limit('invalid'), 20)  # default


class QueryAnalyzerServiceTests(TestCase):
    """Tests for QueryAnalyzerService with vault data."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.service = QueryAnalyzerService()
        self._create_test_vault_items()
    
    def _create_test_vault_items(self):
        """Create test vault items for analysis."""
        from vault.models import EncryptedVaultItem
        from datetime import timedelta
        
        now = timezone.now()
        
        # Recent password
        EncryptedVaultItem.objects.create(
            user=self.user,
            item_id=f'recent-{uuid.uuid4().hex[:8]}',
            item_type='password',
            encrypted_data='encrypted_data_1',
            tags=['work', 'email'],
            created_at=now - timedelta(days=10),
            favorite=True,
        )
        
        # Old password (over 1 year)
        old_item = EncryptedVaultItem.objects.create(
            user=self.user,
            item_id=f'old-{uuid.uuid4().hex[:8]}',
            item_type='password',
            encrypted_data='encrypted_data_2',
            tags=['personal'],
            created_at=now - timedelta(days=400),
        )
        # Force the updated_at to be old
        EncryptedVaultItem.objects.filter(id=old_item.id).update(
            updated_at=now - timedelta(days=400)
        )
        
        # Stale password (6 months)
        stale_item = EncryptedVaultItem.objects.create(
            user=self.user,
            item_id=f'stale-{uuid.uuid4().hex[:8]}',
            item_type='password',
            encrypted_data='encrypted_data_3',
            tags=[],
            created_at=now - timedelta(days=200),
        )
        EncryptedVaultItem.objects.filter(id=stale_item.id).update(
            updated_at=now - timedelta(days=200)
        )
        
        # A secure note (non-password)
        EncryptedVaultItem.objects.create(
            user=self.user,
            item_id=f'note-{uuid.uuid4().hex[:8]}',
            item_type='note',
            encrypted_data='encrypted_note',
            tags=['important'],
        )
    
    def test_analyze_password_health(self):
        """Test password health analysis."""
        result = self.service.analyze_password_health(self.user)
        
        self.assertEqual(result['total_passwords'], 3)
        self.assertIn('health_score', result)
        self.assertIn('old_count', result)
        self.assertGreaterEqual(result['old_count'], 1)
        self.assertIn('summary', result)
    
    def test_analyze_password_health_empty_vault(self):
        """Test health analysis with no passwords."""
        empty_user = User.objects.create_user(
            username='emptyuser',
            email='empty@example.com',
            password='empty123'
        )
        result = self.service.analyze_password_health(empty_user)
        
        self.assertEqual(result['total_passwords'], 0)
        self.assertEqual(result['health_score'], 100)
    
    def test_get_stale_passwords(self):
        """Test retrieving stale passwords."""
        result = self.service.get_stale_passwords(self.user, days_threshold=365)
        
        self.assertGreaterEqual(result['count'], 1)
        # Should not contain actual passwords
        for pwd in result['passwords']:
            self.assertNotIn('encrypted_data', pwd)
            self.assertIn('days_since_update', pwd)
    
    def test_get_risk_assessment(self):
        """Test risk assessment."""
        result = self.service.get_risk_assessment(self.user)
        
        self.assertEqual(result['total_assessed'], 3)
        self.assertIn('high_risk_count', result)
        self.assertIn('medium_risk_count', result)
        self.assertIn('low_risk_count', result)
        total = (
            result['high_risk_count'] +
            result['medium_risk_count'] +
            result['low_risk_count']
        )
        self.assertEqual(total, 3)
    
    def test_search_vault_metadata(self):
        """Test vault metadata search."""
        result = self.service.search_vault_metadata(self.user, 'work')
        
        self.assertGreaterEqual(result['count'], 1)
        # Should find the item tagged 'work'
        for item in result['results']:
            self.assertNotIn('encrypted_data', item)
    
    def test_search_vault_no_results(self):
        """Test vault search with no matches."""
        result = self.service.search_vault_metadata(self.user, 'nonexistent_xyz')
        self.assertEqual(result['count'], 0)
    
    def test_get_security_summary(self):
        """Test security summary generation."""
        result = self.service.get_security_summary(self.user)
        
        self.assertEqual(result['total_items'], 4)  # 3 passwords + 1 note
        self.assertIn('health_score', result)
        self.assertIn('item_type_breakdown', result)
        self.assertIn('summary', result)
    
    def test_build_vault_context(self):
        """Test vault context building for system prompt."""
        context = self.service.build_vault_context(self.user)
        
        self.assertIsInstance(context, str)
        self.assertIn('passwords', context.lower())
        self.assertIn('health score', context.lower())
    
    def test_query_logging(self):
        """Test that queries are logged to AIQueryLog."""
        self.service.analyze_password_health(self.user)
        
        logs = AIQueryLog.objects.filter(user=self.user)
        self.assertGreaterEqual(logs.count(), 1)
        self.assertEqual(logs.first().query_type, 'password_health')


# =============================================================================
# API Tests
# =============================================================================

@override_settings(AI_ASSISTANT_ENABLED=True)
class AIAssistantAPITests(APITestCase):
    """Tests for AI Assistant API endpoints."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='apiuser',
            email='api@example.com',
            password='apipass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_create_session(self):
        """Test creating a conversation session via API."""
        response = self.client.post('/api/ai-assistant/sessions/', {
            'title': 'Test Chat'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['session']['title'], 'Test Chat')
    
    def test_create_session_default_title(self):
        """Test creating session with default title."""
        response = self.client.post('/api/ai-assistant/sessions/', {})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['session']['title'], 'New Conversation')
    
    def test_list_sessions(self):
        """Test listing conversation sessions."""
        ConversationSession.objects.create(user=self.user, title='Chat 1')
        ConversationSession.objects.create(user=self.user, title='Chat 2')
        
        response = self.client.get('/api/ai-assistant/sessions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
    
    def test_list_sessions_excludes_inactive(self):
        """Test that inactive sessions are excluded from list."""
        ConversationSession.objects.create(user=self.user, title='Active')
        ConversationSession.objects.create(
            user=self.user, title='Deleted', is_active=False
        )
        
        response = self.client.get('/api/ai-assistant/sessions/')
        self.assertEqual(response.data['count'], 1)
    
    def test_get_session_detail(self):
        """Test getting session detail with messages."""
        session = ConversationSession.objects.create(
            user=self.user, title='Detail Test'
        )
        ChatMessage.objects.create(
            session=session, role='user', content='Hello'
        )
        
        response = self.client.get(
            f'/api/ai-assistant/sessions/{session.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['session']['messages']), 1)
    
    def test_get_session_not_found(self):
        """Test 404 for non-existent session."""
        fake_id = uuid.uuid4()
        response = self.client.get(
            f'/api/ai-assistant/sessions/{fake_id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_delete_session(self):
        """Test soft-deleting a session."""
        session = ConversationSession.objects.create(
            user=self.user, title='To Delete'
        )
        
        response = self.client.delete(
            f'/api/ai-assistant/sessions/{session.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        session.refresh_from_db()
        self.assertFalse(session.is_active)
    
    def test_session_isolation(self):
        """Test users cannot access other users' sessions."""
        other_user = User.objects.create_user(
            username='other', password='other123'
        )
        other_session = ConversationSession.objects.create(
            user=other_user, title='Private'
        )
        
        response = self.client.get(
            f'/api/ai-assistant/sessions/{other_session.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    @patch('ai_assistant.views.ClaudeService')
    def test_send_message(self, MockClaudeService):
        """Test sending a message and getting AI response."""
        # Mock Claude service
        mock_service = MagicMock()
        mock_service.send_message.return_value = {
            'content': 'Here is my analysis of your security.',
            'tokens_used': 200,
            'model': 'claude-sonnet-4-20250514',
            'input_tokens': 150,
            'output_tokens': 50,
        }
        MockClaudeService.return_value = mock_service
        
        session = ConversationSession.objects.create(
            user=self.user, title='Chat Test'
        )
        
        response = self.client.post(
            f'/api/ai-assistant/sessions/{session.id}/send/',
            {'content': 'Analyze my passwords'}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('user_message', response.data)
        self.assertIn('assistant_message', response.data)
        self.assertEqual(
            response.data['assistant_message']['content'],
            'Here is my analysis of your security.'
        )
    
    def test_send_empty_message(self):
        """Test sending an empty message fails validation."""
        session = ConversationSession.objects.create(
            user=self.user, title='Empty Test'
        )
        
        response = self.client.post(
            f'/api/ai-assistant/sessions/{session.id}/send/',
            {'content': ''}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_send_message_inactive_session(self):
        """Test sending to an inactive session returns 404."""
        session = ConversationSession.objects.create(
            user=self.user, title='Inactive', is_active=False
        )
        
        response = self.client.post(
            f'/api/ai-assistant/sessions/{session.id}/send/',
            {'content': 'Hello'}
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_suggestions_endpoint(self):
        """Test proactive suggestions endpoint."""
        response = self.client.get('/api/ai-assistant/suggestions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('suggestions', response.data)
    
    def test_query_log_endpoint(self):
        """Test query audit log endpoint."""
        response = self.client.get('/api/ai-assistant/query-log/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('logs', response.data)
    
    def test_unauthenticated_access(self):
        """Test that unauthenticated requests are rejected."""
        self.client.force_authenticate(user=None)
        
        response = self.client.get('/api/ai-assistant/sessions/')
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        )


@override_settings(AI_ASSISTANT_ENABLED=False)
class AIAssistantDisabledTests(APITestCase):
    """Tests when AI Assistant feature is disabled."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='disableduser',
            email='disabled@example.com',
            password='disabled123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_sessions_disabled(self):
        """Test sessions endpoint returns 503 when disabled."""
        response = self.client.get('/api/ai-assistant/sessions/')
        self.assertEqual(
            response.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    def test_suggestions_disabled(self):
        """Test suggestions endpoint returns 503 when disabled."""
        response = self.client.get('/api/ai-assistant/suggestions/')
        self.assertEqual(
            response.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE
        )
