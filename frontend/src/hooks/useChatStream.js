import { useState, useRef, useCallback } from 'react';
import { api } from '../services/api';

/**
 * useChatStream
 *
 * Manages all chat message state, streaming, send, stop, and retry logic.
 * Extracted from ChatWindow.jsx so the component only handles rendering.
 *
 * @param {object} opts
 * @param {Function} opts.scrollToBottom - called on each incoming token
 * @param {Function} opts.onConversationCreated - called with new conversation id
 * @param {Function} opts.onRefreshConversations - called after a message completes
 */
export function useChatStream({ scrollToBottom, onConversationCreated, onRefreshConversations }) {
  const [messages, setMessages] = useState([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [lastFailedMessage, setLastFailedMessage] = useState(null);

  const isSendingRef = useRef(false);
  const abortControllerRef = useRef(null);
  const localConvIdRef = useRef(null);  // synchronous — avoids React state lag

  // ── Conversation bootstrapping ──────────────────────────────────────────

  const setConversationId = useCallback((id) => {
    localConvIdRef.current = id || null;
  }, []);

  const ensureActiveConversation = useCallback(async () => {
    if (localConvIdRef.current) return localConvIdRef.current;

    const newConv = await api.createConversation('New Conversation');
    const newId = newConv.conversation_id;
    localConvIdRef.current = newId;
    if (onConversationCreated) onConversationCreated(newId);
    return newId;
  }, [onConversationCreated]);

  // ── Stop generating ─────────────────────────────────────────────────────

  const handleStop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  // ── Core send (used by handleSend and handleRetry) ──────────────────────

  const doSend = async (text, images = []) => {
    setError(null);
    setLastFailedMessage(null);
    setMessages((prev) => [...prev, { role: 'user', content: text, images }]);
    setSending(true);
    isSendingRef.current = true;

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const activeId = await ensureActiveConversation();

      // Optimistic placeholder for the assistant reply
      setMessages((prev) => [...prev, { role: 'assistant', content: '', route_taken: '' }]);

      let streamFailed = false;
      let wasAborted = false;

      try {
        await api.sendMessageStream(activeId, text, images, {
          signal: controller.signal,

          onAgentStart: (data) => {
            if (data.agent || data.message) {
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last?.role === 'assistant') {
                  updated[updated.length - 1] = {
                    ...last,
                    route_taken: data.agent || last.route_taken,
                    status_message: data.message || last.status_message,
                  };
                }
                return updated;
              });
            }
          },

          onToken: (data) => {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last?.role === 'assistant') {
                updated[updated.length - 1] = {
                  ...last,
                  content: last.content + data.content,
                  route_taken: data.agent || last.route_taken,
                };
              }
              return updated;
            });
            scrollToBottom?.();
          },

          onError: () => { streamFailed = true; },
        });

      } catch (streamErr) {
        if (streamErr.name === 'AbortError') {
          wasAborted = true;
        } else {
          streamFailed = true;
        }
      }

      if (wasAborted) {
        // Keep partial content; remove empty placeholder if nothing arrived
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === 'assistant' && !last.content) return prev.slice(0, -1);
          return prev;
        });
      } else if (streamFailed) {
        // SSE failed — fall back to non-streaming REST
        setMessages((prev) => prev.slice(0, -1));
        const res = await api.sendMessage(activeId, text, images);
        setMessages((prev) => [...prev, {
          role: 'assistant',
          content: res.answer,
          route_taken: res.route_taken,
        }]);
      }

      if (onRefreshConversations) setTimeout(onRefreshConversations, 1000);

    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.');
      setLastFailedMessage({ text, images });
      // Remove empty optimistic placeholder
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === 'assistant' && !last.content) return prev.slice(0, -1);
        return prev;
      });
    } finally {
      setSending(false);
      isSendingRef.current = false;
      abortControllerRef.current = null;
    }
  };

  // ── Retry ───────────────────────────────────────────────────────────────

  const handleRetry = async () => {
    if (!lastFailedMessage || sending) return;
    const { text, images } = typeof lastFailedMessage === 'object' ? lastFailedMessage : { text: lastFailedMessage, images: [] };
    // Remove the stale failed user message before re-sending
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last?.role === 'user' && last.content === text) return prev.slice(0, -1);
      return prev;
    });
    await doSend(text, images);
  };

  return {
    messages,
    setMessages,
    sending,
    error,
    setError,
    lastFailedMessage,
    isSendingRef,
    ensureActiveConversation,
    setConversationId,
    doSend,
    handleStop,
    handleRetry,
  };
}
