import React, { useState, useEffect, useRef } from 'react';
import { Send, Cpu, Sparkles, MessageSquare, Plus, Loader2, FileText, X, Menu } from 'lucide-react';
import { MessageItem } from './MessageItem';
import { api } from '../../services/api';

export const ChatWindow = ({ conversationId, activeTitle, onRefreshConversations, onSelectActiveConv, onToggleSidebar }) => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [sending, setSending] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [uploadingFileName, setUploadingFileName] = useState(null);  // shows during upload
  const [activeFiles, setActiveFiles] = useState([]);               // persists after upload
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const isSendingRef = useRef(false);

  // Fetch messages history and ingested documents whenever active conversationId changes
  useEffect(() => {
    setUploadingFileName(null);
    setError(null);

    // If currently sending a message (e.g. creating a new conversation on the fly), preserve optimistic messages
    if (isSendingRef.current) return;

    if (!conversationId) {
      setMessages([]);
      setActiveFiles([]);
      setLoadingHistory(false);
      return;
    }

    const fetchData = async () => {
      setLoadingHistory(true);
      try {
        const [history, docs] = await Promise.all([
          api.getMessages(conversationId),
          api.getDocuments(conversationId).catch(() => []),
        ]);
        setMessages(history);
        if (Array.isArray(docs)) {
          setActiveFiles(docs.map((filename) => ({ name: filename })));
        }
      } catch (err) {
        setError('Failed to load message history.');
      } finally {
        setLoadingHistory(false);
      }
    };
    fetchData();
  }, [conversationId]);

  // Auto-scroll to bottom on new message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  // Ensure an active conversation ID exists in DB before performing actions
  const ensureActiveConversation = async () => {
    if (conversationId) return conversationId;

    const newConv = await api.createConversation('New Conversation');
    const newId = newConv.conversation_id;
    if (onSelectActiveConv) {
      onSelectActiveConv(newId);
    }
    return newId;
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || sending) return;

    const text = inputMessage.trim();
    setInputMessage('');
    setError(null);

    const userMsg = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setSending(true);
    isSendingRef.current = true;

    try {
      const activeId = await ensureActiveConversation();

      // Add optimistic placeholder for assistant response
      setMessages((prev) => [...prev, { role: 'assistant', content: '', route_taken: '' }]);

      let streamFailed = false;

      try {
        await api.sendMessageStream(activeId, text, {
          onAgentStart: (data) => {
            if (data.agent || data.message) {
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last && last.role === 'assistant') {
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
              if (last && last.role === 'assistant') {
                updated[updated.length - 1] = {
                  ...last,
                  content: last.content + data.content,
                  route_taken: data.agent || last.route_taken,
                };
              }
              return updated;
            });
          },
          onError: (data) => {
            streamFailed = true;
          },
        });
      } catch (streamErr) {
        streamFailed = true;
      }

      // Fallback if SSE streaming failed or produced no content
      if (streamFailed) {
        // Remove the empty optimistic message
        setMessages((prev) => prev.slice(0, -1));
        const res = await api.sendMessage(activeId, text);
        setMessages((prev) => [...prev, {
          role: 'assistant',
          content: res.answer,
          route_taken: res.route_taken,
        }]);
      }

      if (onRefreshConversations) {
        setTimeout(() => onRefreshConversations(), 1000);
      }
    } catch (err) {
      setError(err.message || 'Error processing response');
      setMessages((prev) => {
        if (prev.length > 0 && prev[prev.length - 1].role === 'assistant' && !prev[prev.length - 1].content) {
          return prev.slice(0, -1);
        }
        return prev;
      });
    } finally {
      setSending(false);
      isSendingRef.current = false;
    }
  };

  const handleQuickFileSelect = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setIngesting(true);
    setUploadingFileName(file.name);
    setError(null);

    try {
      const activeId = await ensureActiveConversation();
      const res = await api.ingestFile(file, activeId);
      setActiveFiles((prev) => [...prev, { name: file.name }]);
      if (onRefreshConversations) {
        onRefreshConversations();
      }
    } catch (err) {
      const msg = err.message || '';
      if (msg.includes('413') || msg.toLowerCase().includes('too large')) {
        setError('File is too large. Please upload a smaller document (max ~10 MB).');
      } else if (msg.includes('500')) {
        setError('The server could not process this file. Try a different format (PDF, DOCX, TXT).');
      } else {
        setError('File upload failed. Please check the file and try again.');
      }
    } finally {
      setIngesting(false);
      setUploadingFileName(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <main className="chat-main">
      {/* Chat header */}
      <div className="chat-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button className="mobile-menu-btn" onClick={onToggleSidebar} title="Open navigation sidebar">
            <Menu size={20} />
          </button>
          <MessageSquare size={18} style={{ color: '#818cf8' }} />
          <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>{activeTitle || 'New Conversation'}</span>
        </div>
      </div>

      <div className="messages-container">
        {loadingHistory ? (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)' }}>
            Loading message history...
          </div>
        ) : messages.length === 0 ? (
          <div style={{ textAlign: 'center', margin: 'auto', color: 'var(--text-dim)', maxWidth: '440px' }}>
            <Sparkles size={36} style={{ color: 'var(--primary)', marginBottom: '12px' }} />
            <h4 style={{ color: 'var(--text-main)', marginBottom: '8px' }}>Praxis Ready</h4>
            <p style={{ fontSize: '0.9rem' }}>
              Ask a question, request deep research, or upload a document.
            </p>
          </div>
        ) : (
          messages.map((msg, idx) => <MessageItem key={idx} message={msg} />)
        )}

        {sending && (messages.length === 0 || messages[messages.length - 1]?.role !== 'assistant') && (
          <div className="message-bubble assistant">
            <div className="message-avatar">
              <Cpu size={18} className="animate-pulse" />
            </div>
            <div className="message-content" style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="animate-pulse">Thinking...</span>
            </div>
          </div>
        )}

        {error && (
          <div className="auth-alert" style={{ margin: '8px 0' }}>
            <span>{error}</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">

        {/* ── Uploading indicator ── */}
        {ingesting && uploadingFileName && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            fontSize: '0.82rem', color: '#93c5fd',
            background: 'rgba(56, 189, 248, 0.1)',
            border: '1px solid rgba(56, 189, 248, 0.2)',
            padding: '6px 12px', borderRadius: '8px', marginBottom: '8px',
          }}>
            <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
            <span>Uploading <strong>{uploadingFileName}</strong>...</span>
          </div>
        )}

        {/* ── Active files context pills ── */}
        {activeFiles.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '8px' }}>
            {activeFiles.map((f, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                fontSize: '0.78rem', color: '#6ee7b7',
                background: 'rgba(52, 211, 153, 0.1)',
                border: '1px solid rgba(52, 211, 153, 0.25)',
                padding: '4px 10px', borderRadius: '20px',
              }}>
                <FileText size={12} />
                <span>{f.name}</span>
                <button
                  onClick={() => setActiveFiles((prev) => prev.filter((_, idx) => idx !== i))}
                  title="Remove from view"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-dim)', padding: '0 2px', lineHeight: 1 }}
                >
                  <X size={11} />
                </button>
              </div>
            ))}
          </div>
        )}

        <form onSubmit={handleSend} className="chat-input-box">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleQuickFileSelect}
            style={{ display: 'none' }}
            accept=".pdf,.docx,.pptx,.txt,.md"
          />

          <button
            type="button"
            className="attach-btn"
            onClick={() => fileInputRef.current?.click()}
            title="Attach file (PDF, DOCX, TXT) to ingest into session"
            disabled={ingesting || sending}
            style={{
              background: 'rgba(255, 255, 255, 0.06)',
              border: 'none',
              borderRadius: '50%',
              width: '36px',
              height: '36px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              flexShrink: 0,
            }}
          >
            {ingesting ? <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} /> : <Plus size={20} />}
          </button>

          <textarea
            className="chat-textarea"
            placeholder={ingesting ? 'Waiting for document to finish uploading...' : 'Ask me anything...'}
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend(e);
              }
            }}
            rows={1}
            disabled={sending || ingesting}
          />
          <button
            type="submit"
            className="send-btn"
            disabled={!inputMessage.trim() || sending || ingesting}
            title="Send Message"
          >
            <Send size={18} />
          </button>
        </form>
      </div>
    </main>
  );
};
