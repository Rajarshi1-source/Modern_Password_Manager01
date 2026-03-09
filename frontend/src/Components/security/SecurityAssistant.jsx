/**
 * SecurityAssistant.jsx
 * 
 * AI-Powered Conversational Security Assistant
 * 
 * A premium chat interface for natural-language security queries,
 * powered by Claude API. Users can ask about password health,
 * breach status, risk assessments, and get actionable recommendations.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import aiAssistantService from '../../services/aiAssistantService';
import './SecurityAssistant.css';

// Starter prompt suggestions shown in the welcome state
const STARTER_PROMPTS = [
    {
        icon: '🔐',
        text: 'Why is my GitHub password weak?',
    },
    {
        icon: '🕐',
        text: "Which accounts haven't changed passwords in over a year?",
    },
    {
        icon: '🛡️',
        text: 'How does my behavioral recovery work?',
    },
    {
        icon: '⚠️',
        text: 'Which of my accounts are most at risk?',
    },
    {
        icon: '📊',
        text: 'Give me a security overview of my vault',
    },
    {
        icon: '💡',
        text: 'How can I improve my security score?',
    },
];

/**
 * Format a timestamp for display.
 */
const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();

    if (isToday) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleDateString([], {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
};

/**
 * Simple markdown-like rendering for assistant messages.
 * Handles bold, inline code, headers, and lists.
 */
const renderMarkdown = (text) => {
    if (!text) return '';

    // Process each line
    const lines = text.split('\n');
    let html = '';
    let inList = false;

    for (let line of lines) {
        // Headers
        if (line.startsWith('### ')) {
            if (inList) { html += '</ul>'; inList = false; }
            html += `<h3>${line.slice(4)}</h3>`;
            continue;
        }
        if (line.startsWith('## ')) {
            if (inList) { html += '</ul>'; inList = false; }
            html += `<h2>${line.slice(3)}</h2>`;
            continue;
        }
        if (line.startsWith('# ')) {
            if (inList) { html += '</ul>'; inList = false; }
            html += `<h1>${line.slice(2)}</h1>`;
            continue;
        }

        // List items
        if (line.match(/^[-*•]\s/)) {
            if (!inList) { html += '<ul>'; inList = true; }
            line = line.replace(/^[-*•]\s/, '');
            // Inline formatting
            line = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            line = line.replace(/`(.*?)`/g, '<code>$1</code>');
            html += `<li>${line}</li>`;
            continue;
        }

        // Numbered lists
        if (line.match(/^\d+\.\s/)) {
            if (!inList) { html += '<ol>'; inList = true; }
            line = line.replace(/^\d+\.\s/, '');
            line = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            line = line.replace(/`(.*?)`/g, '<code>$1</code>');
            html += `<li>${line}</li>`;
            continue;
        }

        // Close list if we hit a non-list line
        if (inList && line.trim() === '') {
            html += inList ? '</ul>' : '';
            inList = false;
            continue;
        }

        if (inList && !line.match(/^\s/)) {
            html += '</ul>';
            inList = false;
        }

        // Regular paragraph
        if (line.trim()) {
            line = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            line = line.replace(/`(.*?)`/g, '<code>$1</code>');
            html += `<p>${line}</p>`;
        }
    }

    if (inList) html += '</ul>';

    return html;
};

const SecurityAssistant = () => {
    // State
    const [sessions, setSessions] = useState([]);
    const [activeSessionId, setActiveSessionId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [inputValue, setInputValue] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isSending, setIsSending] = useState(false);
    const [suggestions, setSuggestions] = useState([]);
    const [healthScore, setHealthScore] = useState(null);
    const [error, setError] = useState(null);
    const [sidebarOpen, setSidebarOpen] = useState(false);

    // Refs
    const messagesEndRef = useRef(null);
    const textareaRef = useRef(null);

    // =========================================================================
    // Data Loading
    // =========================================================================

    const loadSessions = useCallback(async () => {
        try {
            const data = await aiAssistantService.getSessions();
            setSessions(data.sessions || []);
        } catch (err) {
            console.error('Failed to load sessions:', err);
        }
    }, []);

    const loadSuggestions = useCallback(async () => {
        try {
            const data = await aiAssistantService.getSuggestions();
            setSuggestions(data.suggestions || []);
            setHealthScore(data.health_score);
        } catch (err) {
            console.error('Failed to load suggestions:', err);
        }
    }, []);

    const loadSession = useCallback(async (sessionId) => {
        try {
            setIsLoading(true);
            const data = await aiAssistantService.getSession(sessionId);
            setMessages(data.session?.messages || []);
            setActiveSessionId(sessionId);
            setError(null);
        } catch (err) {
            console.error('Failed to load session:', err);
            setError('Failed to load conversation.');
        } finally {
            setIsLoading(false);
        }
    }, []);

    // Initial load
    useEffect(() => {
        loadSessions();
        loadSuggestions();
    }, [loadSessions, loadSuggestions]);

    // Auto-scroll to bottom on new messages
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isSending]);

    // =========================================================================
    // Session Management
    // =========================================================================

    const handleCreateSession = async () => {
        try {
            const data = await aiAssistantService.createSession();
            const newSession = data.session;
            setSessions(prev => [newSession, ...prev]);
            setActiveSessionId(newSession.id);
            setMessages([]);
            setError(null);
            setSidebarOpen(false);
        } catch (err) {
            console.error('Failed to create session:', err);
            setError('Failed to create new conversation.');
        }
    };

    const handleSelectSession = (sessionId) => {
        loadSession(sessionId);
        setSidebarOpen(false);
    };

    const handleDeleteSession = async (e, sessionId) => {
        e.stopPropagation();
        try {
            await aiAssistantService.deleteSession(sessionId);
            setSessions(prev => prev.filter(s => s.id !== sessionId));
            if (activeSessionId === sessionId) {
                setActiveSessionId(null);
                setMessages([]);
            }
        } catch (err) {
            console.error('Failed to delete session:', err);
        }
    };

    // =========================================================================
    // Message Sending
    // =========================================================================

    const sendMessage = async (content) => {
        if (!content.trim() || isSending) return;

        // Create session if none active
        let sessionId = activeSessionId;
        if (!sessionId) {
            try {
                const data = await aiAssistantService.createSession();
                sessionId = data.session.id;
                setSessions(prev => [data.session, ...prev]);
                setActiveSessionId(sessionId);
            } catch (err) {
                setError('Failed to start conversation.');
                return;
            }
        }

        // Add user message optimistically
        const tempUserMsg = {
            id: `temp-${Date.now()}`,
            role: 'user',
            content: content.trim(),
            timestamp: new Date().toISOString(),
        };
        setMessages(prev => [...prev, tempUserMsg]);
        setInputValue('');
        setIsSending(true);
        setError(null);

        // Reset textarea height
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
        }

        try {
            const data = await aiAssistantService.sendMessage(sessionId, content.trim());

            // Replace temp message with real one and add assistant response
            setMessages(prev => {
                const filtered = prev.filter(m => m.id !== tempUserMsg.id);
                return [
                    ...filtered,
                    data.user_message,
                    data.assistant_message,
                ];
            });

            // Update session title in sidebar
            loadSessions();

        } catch (err) {
            console.error('Failed to send message:', err);
            const errorMsg = err.response?.data?.error || 'Failed to get a response. Please try again.';
            setError(errorMsg);
        } finally {
            setIsSending(false);
        }
    };

    const handleSend = () => {
        sendMessage(inputValue);
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleTextareaChange = (e) => {
        setInputValue(e.target.value);
        // Auto-resize textarea
        e.target.style.height = 'auto';
        e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
    };

    const handleStarterPrompt = (text) => {
        sendMessage(text);
    };

    const handleSuggestionClick = (action) => {
        sendMessage(action);
    };

    // =========================================================================
    // Health Badge
    // =========================================================================

    const getHealthBadgeClass = () => {
        if (healthScore === null) return '';
        if (healthScore >= 80) return 'good';
        if (healthScore >= 50) return 'warning';
        return 'danger';
    };

    const getHealthLabel = () => {
        if (healthScore === null) return '';
        if (healthScore >= 80) return `✅ ${healthScore}/100`;
        if (healthScore >= 50) return `⚠️ ${healthScore}/100`;
        return `🔴 ${healthScore}/100`;
    };

    // =========================================================================
    // Render
    // =========================================================================

    return (
        <div className="security-assistant" id="security-assistant">
            {/* --- Sidebar --- */}
            <aside className={`sa-sidebar ${sidebarOpen ? 'open' : ''}`}>
                <div className="sa-sidebar-header">
                    <h2>
                        <span className="sa-icon">🧠</span>
                        Security Assistant
                    </h2>
                    <p>AI-powered security advisor</p>
                    <button
                        className="sa-new-chat-btn"
                        onClick={handleCreateSession}
                        id="sa-new-chat"
                    >
                        ✨ New Conversation
                    </button>
                </div>

                <div className="sa-session-list">
                    {sessions.length === 0 && (
                        <p style={{
                            textAlign: 'center',
                            color: 'var(--sa-text-dim)',
                            fontSize: '13px',
                            padding: '20px 12px'
                        }}>
                            No conversations yet.<br />Start one above!
                        </p>
                    )}
                    {sessions.map(session => (
                        <div
                            key={session.id}
                            className={`sa-session-item ${session.id === activeSessionId ? 'active' : ''}`}
                            onClick={() => handleSelectSession(session.id)}
                        >
                            <div className="sa-session-row">
                                <div className="sa-session-title">
                                    {session.title || 'New Conversation'}
                                </div>
                                <button
                                    className="sa-session-delete"
                                    onClick={(e) => handleDeleteSession(e, session.id)}
                                    title="Delete conversation"
                                >
                                    🗑️
                                </button>
                            </div>
                            <div className="sa-session-meta">
                                <span>{session.message_count || 0} messages</span>
                                <span>•</span>
                                <span>{formatTime(session.last_activity)}</span>
                            </div>
                        </div>
                    ))}
                </div>
            </aside>

            {/* --- Main Chat Area --- */}
            <main className="sa-chat-area">
                {/* Chat Header */}
                <div className="sa-chat-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <button
                            className="sa-mobile-toggle"
                            onClick={() => setSidebarOpen(!sidebarOpen)}
                            id="sa-sidebar-toggle"
                        >
                            ☰
                        </button>
                        <h3>
                            {activeSessionId
                                ? (sessions.find(s => s.id === activeSessionId)?.title || 'Chat')
                                : 'Security Assistant'
                            }
                        </h3>
                    </div>
                    {healthScore !== null && (
                        <span className={`sa-health-badge ${getHealthBadgeClass()}`}>
                            {getHealthLabel()}
                        </span>
                    )}
                </div>

                {/* Suggestion Cards */}
                {suggestions.length > 0 && !activeSessionId && (
                    <div className="sa-suggestions" id="sa-suggestions">
                        {suggestions.map((suggestion, idx) => (
                            <div
                                key={idx}
                                className={`sa-suggestion-card ${suggestion.type}`}
                                onClick={() => handleSuggestionClick(suggestion.action)}
                            >
                                <div className="sa-suggestion-title">
                                    {suggestion.icon} {suggestion.title}
                                </div>
                                <p className="sa-suggestion-desc">
                                    {suggestion.description}
                                </p>
                            </div>
                        ))}
                    </div>
                )}

                {/* Messages or Welcome */}
                {!activeSessionId && messages.length === 0 ? (
                    <div className="sa-welcome" id="sa-welcome">
                        <div className="sa-welcome-icon">🧠</div>
                        <h2>Security Assistant</h2>
                        <p>
                            Ask me anything about your password security. I can analyze your vault,
                            identify risks, explain security concepts, and help you stay safe online.
                        </p>
                        <div className="sa-starter-prompts">
                            {STARTER_PROMPTS.map((prompt, idx) => (
                                <button
                                    key={idx}
                                    className="sa-starter-prompt"
                                    onClick={() => handleStarterPrompt(prompt.text)}
                                    id={`sa-starter-${idx}`}
                                >
                                    <span className="sa-prompt-icon">{prompt.icon}</span>
                                    <span className="sa-prompt-text">{prompt.text}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                ) : (
                    <div className="sa-messages" id="sa-messages">
                        {isLoading ? (
                            <div className="sa-loading">
                                <div className="sa-spinner" />
                                Loading conversation...
                            </div>
                        ) : (
                            <>
                                {messages.map((msg) => (
                                    <div
                                        key={msg.id}
                                        className={`sa-message ${msg.role}`}
                                    >
                                        {msg.role !== 'system' && (
                                            <div className="sa-message-avatar">
                                                {msg.role === 'user' ? '👤' : '🧠'}
                                            </div>
                                        )}
                                        <div>
                                            {msg.role === 'assistant' ? (
                                                <div
                                                    className="sa-message-content"
                                                    dangerouslySetInnerHTML={{
                                                        __html: renderMarkdown(msg.content)
                                                    }}
                                                />
                                            ) : (
                                                <div className="sa-message-content">
                                                    {msg.content}
                                                </div>
                                            )}
                                            {msg.timestamp && (
                                                <div className="sa-message-time">
                                                    {formatTime(msg.timestamp)}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                ))}

                                {/* Typing Indicator */}
                                {isSending && (
                                    <div className="sa-typing-indicator">
                                        <div className="sa-message-avatar" style={{
                                            background: 'linear-gradient(135deg, #0ea5e9, #22d3ee)',
                                            width: 32, height: 32, borderRadius: 8,
                                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                                            fontSize: 16
                                        }}>
                                            🧠
                                        </div>
                                        <div className="sa-typing-dots">
                                            <span /><span /><span />
                                        </div>
                                    </div>
                                )}

                                <div ref={messagesEndRef} />
                            </>
                        )}
                    </div>
                )}

                {/* Error Message */}
                {error && (
                    <div className="sa-error" id="sa-error">
                        <span className="sa-error-text">⚠️ {error}</span>
                        <button
                            className="sa-error-retry"
                            onClick={() => setError(null)}
                        >
                            Dismiss
                        </button>
                    </div>
                )}

                {/* Input Area */}
                <div className="sa-input-area">
                    <div className="sa-input-wrapper">
                        <textarea
                            ref={textareaRef}
                            value={inputValue}
                            onChange={handleTextareaChange}
                            onKeyDown={handleKeyDown}
                            placeholder="Ask about your password security..."
                            rows={1}
                            disabled={isSending}
                            id="sa-message-input"
                        />
                        <button
                            className="sa-send-btn"
                            onClick={handleSend}
                            disabled={!inputValue.trim() || isSending}
                            title="Send message"
                            id="sa-send-button"
                        >
                            ➤
                        </button>
                    </div>
                    <div className="sa-input-hint">
                        Press Enter to send, Shift+Enter for new line
                    </div>
                </div>
            </main>
        </div>
    );
};

export default SecurityAssistant;
