import React, { useState, useEffect, useRef } from 'react';
import { Send, FilePlus, Cpu, Sparkles, MessageSquare, Plus, Paperclip, CheckCircle2, Loader2 } from 'lucide-react';
import { MessageItem } from './MessageItem';
import { api } from '../../services/api';

export const ChatWindow = ({ conversationId, activeTitle, onOpenIngest, onRefreshConversations }) => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [sending, setSending] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [ingestNotice, setIngestNotice] = useState(null);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  // Fetch messages history whenever active conversationId changes
  useEffect(() => {
    if (!conversationId) return;

    const fetchHistory = async () => {
      setLoadingHistory(true);
      setError(null);
      try {
        const history = await api.getMessages(conversationId);
        setMessages(history);
      } catch (err) {
        console.error('Failed to load messages:', err);
        setError('Failed to load message history.');
      } finally {
        setLoadingHistory(false);
      }
    };

    fetchHistory();
  }, [conversationId]);

  // Auto-scroll to bottom on new message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || sending || !conversationId) return;

    const text = inputMessage.trim();
    setInputMessage('');
    setError(null);

    // Optimistically add user message to thread
    const userMsg = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setSending(true);

    try {
      const res = await api.sendMessage(conversationId, text);
      const assistantMsg = {
        role: 'assistant',
        content: res.answer,
        route_taken: res.route_taken,
      };
      setMessages((prev) => [...prev, assistantMsg]);

      // If this was the first turn in a 'New Conversation', refresh sidebar titles after short delay
      if (messages.length <= 1 && onRefreshConversations) {
        setTimeout(() => onRefreshConversations(), 1500);
      }
    } catch (err) {
      console.error('Failed to send message:', err);
      setError(err.message || 'Error processing response');
    } finally {
      setSending(false);
    }
  };

  const handleQuickFileSelect = async (e) => {
    const file = e.target.files[0];
    if (!file || !conversationId) return;

    setIngesting(true);
    setIngestNotice(null);
    setError(null);

    try {
      const res = await api.ingestFile(file, conversationId);
      setIngestNotice(`Ingested "${file.name}" (${res.documents_stored} chunks)`);
      setTimeout(() => setIngestNotice(null), 4000);
    } catch (err) {
      console.error('Quick ingestion error:', err);
      setError(err.message || 'File ingestion failed');
    } finally {
      setIngesting(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  if (!conversationId) {
    return (
      <div className="chat-main" style={{ justifyContent: 'center', alignItems: 'center', textAlign: 'center' }}>
        <div style={{ color: 'var(--text-dim)', maxWidth: '400px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
          <div className="brand-icon" style={{ width: '56px', height: '56px' }}>
            <Cpu size={32} />
          </div>
          <h3 style={{ color: 'var(--text-main)' }}>No Conversation Selected</h3>
          <p style={{ fontSize: '0.9rem' }}>Select a conversation from the sidebar or start a new chat to begin prompting the multi-agent AI engine.</p>
        </div>
      </div>
    );
  }

  return (
    <main className="chat-main">
      <div className="chat-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <MessageSquare size={18} style={{ color: '#38bdf8' }} />
          <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>{activeTitle || 'Active Session'}</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', background: 'rgba(255,255,255,0.05)', padding: '2px 8px', borderRadius: '4px', fontFamily: 'var(--font-mono)' }}>
            {conversationId.substring(0, 8)}...
          </span>
        </div>

        <button
          className="btn btn-secondary"
          style={{ padding: '6px 14px', fontSize: '0.85rem' }}
          onClick={onOpenIngest}
        >
          <FilePlus size={16} style={{ color: '#34d399' }} />
          <span>Ingest Doc</span>
        </button>
      </div>

      <div className="messages-container">
        {loadingHistory ? (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)' }}>
            Loading message history...
          </div>
        ) : messages.length === 0 ? (
          <div style={{ textAlign: 'center', margin: 'auto', color: 'var(--text-dim)', maxWidth: '440px' }}>
            <Sparkles size={36} style={{ color: 'var(--primary)', marginBottom: '12px' }} />
            <h4 style={{ color: 'var(--text-main)', marginBottom: '8px' }}>Praxis AI Ready</h4>
            <p style={{ fontSize: '0.9rem' }}>
              Ask a question, request deep research, or upload a document to trigger the Knowledge Team.
            </p>
          </div>
        ) : (
          messages.map((msg, idx) => <MessageItem key={idx} message={msg} />)
        )}

        {sending && (
          <div className="message-bubble assistant">
            <div className="message-avatar">
              <Cpu size={18} className="animate-pulse" />
            </div>
            <div className="message-content" style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="animate-pulse">CEO Orchestrator is analyzing history & delegating...</span>
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
        {ingestNotice && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', color: '#6ee7b7', background: 'rgba(52, 211, 153, 0.15)', padding: '6px 12px', borderRadius: '8px', marginBottom: '8px' }}>
            <CheckCircle2 size={16} />
            <span>{ingestNotice}</span>
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
            {ingesting ? <Loader2 size={18} className="animate-pulse" /> : <Plus size={20} />}
          </button>

          <textarea
            className="chat-textarea"
            placeholder="Ask anything, attach a document (+), or request deep research..."
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend(e);
              }
            }}
            rows={1}
            disabled={sending}
          />
          <button
            type="submit"
            className="send-btn"
            disabled={!inputMessage.trim() || sending}
            title="Send Message"
          >
            <Send size={18} />
          </button>
        </form>
      </div>
    </main>
  );
};
