/**
 * AIAssistantService.js
 * 
 * Mobile service for the AI-powered security assistant.
 * Communicates with the backend API for chat sessions and suggestions.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE_URL = 'http://10.0.2.2:8000'; // Android emulator localhost
const AI_ASSISTANT_PATH = '/api/ai-assistant';

/**
 * Get auth headers for API requests.
 */
const getAuthHeaders = async () => {
  const token = await AsyncStorage.getItem('accessToken');
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
  };
};

/**
 * Make an authenticated API request.
 */
const apiRequest = async (method, path, body = null) => {
  const headers = await getAuthHeaders();
  const url = `${API_BASE_URL}${AI_ASSISTANT_PATH}${path}`;
  
  const options = {
    method,
    headers,
  };
  
  if (body) {
    options.body = JSON.stringify(body);
  }
  
  const response = await fetch(url, options);
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || `Request failed with status ${response.status}`);
  }
  
  return response.json();
};

const AIAssistantService = {
  /**
   * List all active conversation sessions.
   */
  getSessions: () => apiRequest('GET', '/sessions/'),

  /**
   * Create a new conversation session.
   */
  createSession: (title = 'New Conversation') => 
    apiRequest('POST', '/sessions/', { title }),

  /**
   * Get a session with all its messages.
   */
  getSession: (sessionId) => apiRequest('GET', `/sessions/${sessionId}/`),

  /**
   * Delete (soft-delete) a conversation session.
   */
  deleteSession: (sessionId) => apiRequest('DELETE', `/sessions/${sessionId}/`),

  /**
   * Send a message and get an AI response.
   */
  sendMessage: (sessionId, content) => 
    apiRequest('POST', `/sessions/${sessionId}/send/`, { content }),

  /**
   * Get proactive security suggestions.
   */
  getSuggestions: () => apiRequest('GET', '/suggestions/'),

  /**
   * Get AI query audit logs.
   */
  getQueryLog: () => apiRequest('GET', '/query-log/'),
};

export default AIAssistantService;
