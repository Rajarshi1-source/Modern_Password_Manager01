/**
 * AI Assistant Service
 * 
 * API client for the conversational security assistant.
 * Handles session management, message sending, and proactive suggestions.
 */

import api from './api';

const AI_ASSISTANT_BASE = '/api/ai-assistant';

const aiAssistantService = {
  // =========================================================================
  // Session Management
  // =========================================================================

  /**
   * List all active conversation sessions.
   * @returns {Promise<Object>} { status, count, sessions[] }
   */
  getSessions: async () => {
    const response = await api.get(`${AI_ASSISTANT_BASE}/sessions/`);
    return response.data;
  },

  /**
   * Create a new conversation session.
   * @param {string} title - Optional session title
   * @returns {Promise<Object>} { status, session }
   */
  createSession: async (title = 'New Conversation') => {
    const response = await api.post(`${AI_ASSISTANT_BASE}/sessions/`, { title });
    return response.data;
  },

  /**
   * Get a session with all its messages.
   * @param {string} sessionId - UUID of the session
   * @returns {Promise<Object>} { status, session }
   */
  getSession: async (sessionId) => {
    const response = await api.get(`${AI_ASSISTANT_BASE}/sessions/${sessionId}/`);
    return response.data;
  },

  /**
   * Delete (soft-delete) a conversation session.
   * @param {string} sessionId - UUID of the session
   * @returns {Promise<Object>} { status, message }
   */
  deleteSession: async (sessionId) => {
    const response = await api.delete(`${AI_ASSISTANT_BASE}/sessions/${sessionId}/`);
    return response.data;
  },

  // =========================================================================
  // Chat / Messaging
  // =========================================================================

  /**
   * Send a message in a conversation and get an AI response.
   * @param {string} sessionId - UUID of the session
   * @param {string} content - The user's message
   * @returns {Promise<Object>} { status, user_message, assistant_message }
   */
  sendMessage: async (sessionId, content) => {
    const response = await api.post(
      `${AI_ASSISTANT_BASE}/sessions/${sessionId}/send/`,
      { content }
    );
    return response.data;
  },

  // =========================================================================
  // Proactive Suggestions
  // =========================================================================

  /**
   * Get proactive security suggestions based on vault analysis.
   * @returns {Promise<Object>} { status, suggestions[], health_score, total_passwords }
   */
  getSuggestions: async () => {
    const response = await api.get(`${AI_ASSISTANT_BASE}/suggestions/`);
    return response.data;
  },

  // =========================================================================
  // Audit Trail
  // =========================================================================

  /**
   * Get AI query audit logs.
   * @returns {Promise<Object>} { status, count, logs[] }
   */
  getQueryLog: async () => {
    const response = await api.get(`${AI_ASSISTANT_BASE}/query-log/`);
    return response.data;
  },
};

export default aiAssistantService;
