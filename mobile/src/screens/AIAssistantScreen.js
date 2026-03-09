/**
 * AIAssistantScreen.js
 * 
 * React Native chat screen for the AI-powered security assistant.
 * Provides a mobile-native chat experience for security queries.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  SafeAreaView,
  Animated,
  Alert,
  ScrollView,
} from 'react-native';
import AIAssistantService from '../services/AIAssistantService';

// Starter prompts shown when no conversation is active
const STARTER_PROMPTS = [
  { icon: '🔐', text: 'Why is my GitHub password weak?' },
  { icon: '🕐', text: "Which accounts haven't changed passwords?" },
  { icon: '🛡️', text: 'How does behavioral recovery work?' },
  { icon: '⚠️', text: 'Which accounts are most at risk?' },
  { icon: '📊', text: 'Give me a security overview' },
  { icon: '💡', text: 'How to improve my security score?' },
];

/**
 * Format timestamp for display.
 */
const formatTime = (timestamp) => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

/**
 * Message bubble component.
 */
const MessageBubble = ({ message }) => {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  const fadeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: 300,
      useNativeDriver: true,
    }).start();
  }, [fadeAnim]);

  if (isSystem) {
    return (
      <Animated.View style={[styles.systemMessage, { opacity: fadeAnim }]}>
        <Text style={styles.systemMessageText}>⚠️ {message.content}</Text>
      </Animated.View>
    );
  }

  return (
    <Animated.View
      style={[
        styles.messageBubble,
        isUser ? styles.userBubble : styles.assistantBubble,
        { opacity: fadeAnim, transform: [{ translateY: fadeAnim.interpolate({
          inputRange: [0, 1],
          outputRange: [10, 0],
        })}]},
      ]}
    >
      <View style={[
        styles.avatar,
        isUser ? styles.userAvatar : styles.assistantAvatar,
      ]}>
        <Text style={styles.avatarText}>{isUser ? '👤' : '🧠'}</Text>
      </View>
      <View style={[
        styles.messageContent,
        isUser ? styles.userContent : styles.assistantContent,
      ]}>
        <Text style={[
          styles.messageText,
          isUser ? styles.userText : styles.assistantText,
        ]}>
          {message.content}
        </Text>
        {message.timestamp && (
          <Text style={styles.messageTime}>
            {formatTime(message.timestamp)}
          </Text>
        )}
      </View>
    </Animated.View>
  );
};

/**
 * Typing indicator component.
 */
const TypingIndicator = () => {
  const dots = [
    useRef(new Animated.Value(0)).current,
    useRef(new Animated.Value(0)).current,
    useRef(new Animated.Value(0)).current,
  ];

  useEffect(() => {
    const animations = dots.map((dot, index) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(index * 200),
          Animated.timing(dot, {
            toValue: 1,
            duration: 400,
            useNativeDriver: true,
          }),
          Animated.timing(dot, {
            toValue: 0,
            duration: 400,
            useNativeDriver: true,
          }),
        ])
      )
    );
    animations.forEach(a => a.start());
    return () => animations.forEach(a => a.stop());
  }, []);

  return (
    <View style={styles.typingContainer}>
      <View style={styles.assistantAvatar}>
        <Text style={styles.avatarText}>🧠</Text>
      </View>
      <View style={styles.typingDots}>
        {dots.map((dot, index) => (
          <Animated.View
            key={index}
            style={[
              styles.typingDot,
              {
                transform: [{
                  translateY: dot.interpolate({
                    inputRange: [0, 1],
                    outputRange: [0, -8],
                  }),
                }],
                opacity: dot.interpolate({
                  inputRange: [0, 1],
                  outputRange: [0.4, 1],
                }),
              },
            ]}
          />
        ))}
      </View>
    </View>
  );
};

/**
 * Main AI Assistant Screen.
 */
const AIAssistantScreen = ({ navigation }) => {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [healthScore, setHealthScore] = useState(null);
  const [error, setError] = useState(null);
  const flatListRef = useRef(null);

  // Load suggestions on mount
  useEffect(() => {
    loadSuggestions();
  }, []);

  const loadSuggestions = async () => {
    try {
      const data = await AIAssistantService.getSuggestions();
      setSuggestions(data.suggestions || []);
      setHealthScore(data.health_score);
    } catch (err) {
      console.log('Failed to load suggestions:', err.message);
    }
  };

  const createSession = async () => {
    try {
      const data = await AIAssistantService.createSession();
      setActiveSessionId(data.session.id);
      return data.session.id;
    } catch (err) {
      throw new Error('Failed to create conversation');
    }
  };

  const sendMessage = async (content) => {
    if (!content.trim() || isSending) return;

    let sessionId = activeSessionId;
    if (!sessionId) {
      try {
        sessionId = await createSession();
      } catch (err) {
        setError(err.message);
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
    setInputText('');
    setIsSending(true);
    setError(null);

    try {
      const data = await AIAssistantService.sendMessage(sessionId, content.trim());

      setMessages(prev => {
        const filtered = prev.filter(m => m.id !== tempUserMsg.id);
        return [...filtered, data.user_message, data.assistant_message];
      });
    } catch (err) {
      setError(err.message || 'Failed to get a response. Please try again.');
    } finally {
      setIsSending(false);
    }
  };

  const handleSend = () => sendMessage(inputText);

  const handleStarterPrompt = (text) => sendMessage(text);

  const handleSuggestionPress = (action) => sendMessage(action);

  // Auto-scroll to bottom
  useEffect(() => {
    if (messages.length > 0) {
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  }, [messages, isSending]);

  const getHealthColor = () => {
    if (!healthScore) return '#6366f1';
    if (healthScore >= 80) return '#10b981';
    if (healthScore >= 50) return '#f59e0b';
    return '#ef4444';
  };

  // Render welcome screen or chat
  const renderContent = () => {
    if (messages.length === 0 && !activeSessionId) {
      return (
        <ScrollView
          style={styles.welcomeContainer}
          contentContainerStyle={styles.welcomeContent}
        >
          <Text style={styles.welcomeIcon}>🧠</Text>
          <Text style={styles.welcomeTitle}>Security Assistant</Text>
          <Text style={styles.welcomeSubtitle}>
            Ask me anything about your password security. I can analyze your vault,
            identify risks, and help you stay safe.
          </Text>

          {/* Suggestions */}
          {suggestions.length > 0 && (
            <View style={styles.suggestionsContainer}>
              {suggestions.map((suggestion, idx) => (
                <TouchableOpacity
                  key={idx}
                  style={[styles.suggestionCard, {
                    borderLeftColor: suggestion.type === 'danger' ? '#ef4444' :
                      suggestion.type === 'warning' ? '#f59e0b' :
                      suggestion.type === 'success' ? '#10b981' : '#6366f1',
                  }]}
                  onPress={() => handleSuggestionPress(suggestion.action)}
                >
                  <Text style={styles.suggestionTitle}>
                    {suggestion.icon} {suggestion.title}
                  </Text>
                  <Text style={styles.suggestionDesc}>
                    {suggestion.description}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          )}

          {/* Starter Prompts */}
          <View style={styles.starterGrid}>
            {STARTER_PROMPTS.map((prompt, idx) => (
              <TouchableOpacity
                key={idx}
                style={styles.starterPrompt}
                onPress={() => handleStarterPrompt(prompt.text)}
              >
                <Text style={styles.starterIcon}>{prompt.icon}</Text>
                <Text style={styles.starterText}>{prompt.text}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </ScrollView>
      );
    }

    return (
      <FlatList
        ref={flatListRef}
        data={messages}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <MessageBubble message={item} />}
        contentContainerStyle={styles.messageList}
        ListFooterComponent={isSending ? <TypingIndicator /> : null}
        onContentSizeChange={() => {
          flatListRef.current?.scrollToEnd({ animated: true });
        }}
      />
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <TouchableOpacity
            onPress={() => navigation.goBack()}
            style={styles.backButton}
          >
            <Text style={styles.backButtonText}>←</Text>
          </TouchableOpacity>
          <View>
            <Text style={styles.headerTitle}>Security Assistant</Text>
            <Text style={styles.headerSubtitle}>AI-powered advisor</Text>
          </View>
        </View>
        {healthScore !== null && (
          <View style={[styles.healthBadge, { borderColor: getHealthColor() }]}>
            <Text style={[styles.healthText, { color: getHealthColor() }]}>
              {healthScore}/100
            </Text>
          </View>
        )}
      </View>

      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.chatArea}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
      >
        {isLoading ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color="#6366f1" />
            <Text style={styles.loadingText}>Loading...</Text>
          </View>
        ) : (
          renderContent()
        )}

        {/* Error */}
        {error && (
          <View style={styles.errorContainer}>
            <Text style={styles.errorText}>⚠️ {error}</Text>
            <TouchableOpacity onPress={() => setError(null)}>
              <Text style={styles.errorDismiss}>Dismiss</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Input Area */}
        <View style={styles.inputArea}>
          <View style={styles.inputWrapper}>
            <TextInput
              style={styles.textInput}
              value={inputText}
              onChangeText={setInputText}
              placeholder="Ask about your security..."
              placeholderTextColor="#64748b"
              multiline
              maxLength={5000}
              editable={!isSending}
              onSubmitEditing={handleSend}
              blurOnSubmit={false}
            />
            <TouchableOpacity
              style={[
                styles.sendButton,
                (!inputText.trim() || isSending) && styles.sendButtonDisabled,
              ]}
              onPress={handleSend}
              disabled={!inputText.trim() || isSending}
            >
              <Text style={styles.sendButtonText}>➤</Text>
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

// =============================================================================
// Styles
// =============================================================================

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0f1e',
  },

  // Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(99, 102, 241, 0.15)',
    backgroundColor: 'rgba(15, 23, 42, 0.85)',
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  backButton: {
    padding: 4,
  },
  backButtonText: {
    fontSize: 24,
    color: '#e2e8f0',
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: '#e2e8f0',
  },
  headerSubtitle: {
    fontSize: 12,
    color: '#64748b',
    marginTop: 1,
  },
  healthBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 16,
    borderWidth: 1,
  },
  healthText: {
    fontSize: 12,
    fontWeight: '600',
  },

  // Chat Area
  chatArea: {
    flex: 1,
  },
  messageList: {
    padding: 16,
    paddingBottom: 8,
  },

  // Message Bubbles
  messageBubble: {
    flexDirection: 'row',
    marginBottom: 12,
    maxWidth: '85%',
  },
  userBubble: {
    alignSelf: 'flex-end',
    flexDirection: 'row-reverse',
  },
  assistantBubble: {
    alignSelf: 'flex-start',
  },
  avatar: {
    width: 32,
    height: 32,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: 8,
  },
  userAvatar: {
    backgroundColor: '#6366f1',
  },
  assistantAvatar: {
    backgroundColor: '#0ea5e9',
    width: 32,
    height: 32,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: 16,
  },
  messageContent: {
    borderRadius: 12,
    padding: 12,
    maxWidth: '80%',
  },
  userContent: {
    backgroundColor: '#6366f1',
    borderBottomRightRadius: 4,
  },
  assistantContent: {
    backgroundColor: 'rgba(30, 41, 59, 0.9)',
    borderWidth: 1,
    borderColor: 'rgba(99, 102, 241, 0.15)',
    borderBottomLeftRadius: 4,
  },
  messageText: {
    fontSize: 14,
    lineHeight: 21,
  },
  userText: {
    color: '#ffffff',
  },
  assistantText: {
    color: '#e2e8f0',
  },
  messageTime: {
    fontSize: 10,
    color: '#64748b',
    marginTop: 4,
  },

  // System Messages
  systemMessage: {
    alignSelf: 'center',
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(239, 68, 68, 0.25)',
    borderRadius: 8,
    padding: 8,
    marginVertical: 8,
  },
  systemMessageText: {
    color: '#ef4444',
    fontSize: 13,
    textAlign: 'center',
  },

  // Typing Indicator
  typingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 8,
    gap: 8,
  },
  typingDots: {
    flexDirection: 'row',
    backgroundColor: 'rgba(30, 41, 59, 0.9)',
    borderWidth: 1,
    borderColor: 'rgba(99, 102, 241, 0.15)',
    borderRadius: 12,
    padding: 12,
    gap: 4,
  },
  typingDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#818cf8',
  },

  // Welcome Screen
  welcomeContainer: {
    flex: 1,
  },
  welcomeContent: {
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingTop: 40,
    paddingBottom: 24,
  },
  welcomeIcon: {
    fontSize: 56,
    marginBottom: 16,
  },
  welcomeTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: '#818cf8',
    marginBottom: 8,
  },
  welcomeSubtitle: {
    fontSize: 14,
    color: '#94a3b8',
    textAlign: 'center',
    lineHeight: 21,
    marginBottom: 24,
    maxWidth: 340,
  },

  // Suggestions
  suggestionsContainer: {
    width: '100%',
    marginBottom: 20,
  },
  suggestionCard: {
    backgroundColor: 'rgba(15, 23, 42, 0.85)',
    borderWidth: 1,
    borderColor: 'rgba(99, 102, 241, 0.15)',
    borderLeftWidth: 3,
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
  },
  suggestionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#e2e8f0',
    marginBottom: 4,
  },
  suggestionDesc: {
    fontSize: 12,
    color: '#94a3b8',
    lineHeight: 17,
  },

  // Starter Prompts
  starterGrid: {
    width: '100%',
    gap: 8,
  },
  starterPrompt: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: 'rgba(15, 23, 42, 0.85)',
    borderWidth: 1,
    borderColor: 'rgba(99, 102, 241, 0.15)',
    borderRadius: 12,
    padding: 14,
  },
  starterIcon: {
    fontSize: 20,
  },
  starterText: {
    fontSize: 13,
    color: '#e2e8f0',
    flex: 1,
  },

  // Input Area
  inputArea: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: 'rgba(99, 102, 241, 0.15)',
    backgroundColor: 'rgba(15, 23, 42, 0.85)',
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: 'rgba(15, 23, 42, 0.9)',
    borderWidth: 1,
    borderColor: 'rgba(99, 102, 241, 0.15)',
    borderRadius: 12,
    paddingLeft: 14,
    paddingRight: 4,
    paddingVertical: 4,
  },
  textInput: {
    flex: 1,
    color: '#e2e8f0',
    fontSize: 14,
    maxHeight: 100,
    paddingVertical: 8,
    fontFamily: Platform.OS === 'ios' ? 'System' : 'Roboto',
  },
  sendButton: {
    width: 40,
    height: 40,
    borderRadius: 8,
    backgroundColor: '#6366f1',
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 8,
  },
  sendButtonDisabled: {
    opacity: 0.4,
  },
  sendButtonText: {
    color: '#ffffff',
    fontSize: 18,
  },

  // Error
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(239, 68, 68, 0.25)',
    borderRadius: 8,
    marginHorizontal: 16,
    marginBottom: 8,
    padding: 10,
  },
  errorText: {
    color: '#ef4444',
    fontSize: 13,
    flex: 1,
  },
  errorDismiss: {
    color: '#ef4444',
    fontSize: 12,
    fontWeight: '600',
    paddingHorizontal: 10,
    paddingVertical: 4,
  },

  // Loading
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  loadingText: {
    color: '#94a3b8',
    fontSize: 14,
  },
});

export default AIAssistantScreen;
