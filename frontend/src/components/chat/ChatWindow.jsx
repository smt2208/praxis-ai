import React, { useState, useEffect, useRef } from 'react';
import { Send, Cpu, Sparkles, MessageSquare, Plus, CheckCircle2, Loader2, FileText, X } from 'lucide-react';
import { MessageItem } from './MessageItem';
import { api } from '../../services/api';

export const ChatWindow = ({ conversationId, activeTitle, onRefreshConversations }) => {
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

  // Reset files when conversation changes
  useEffect(() => {
    setActiveFiles([]);
    setUploadingFileName(null);
    setError(null);
  }, [conversationId]);

  // Fetch messages history whenever active conversationId changes
  useEffect(() => {
    if (!conversationId) return;
    const fetchHistory = async () => {
      setLoadingHistory(true);
      try {
        const history = await api.getMessages(conversationId);
        setMessages(history);
      } catch (err) {
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

      if (messages.length <= 1 && onRefreshConversations) {
        setTimeout(() => onRefreshConversations(), 1500);
      }
    } catch (err) {
      setError(err.message || 'Error processing response');
    } finally {
      setSending(false);
    }
  };

  const handleQuickFileSelect = async (e) => {
    const file = e.target.files[0];
    if (!file || !conversationId) return;

    setIngesting(true);
    setUploadingFileName(file.name);
    setError(null);

    try {
      const res = await api.ingestFile(file, conversationId);
      // Add to persistent context list
      setActiveFiles((prev) => [...prev, { name: file.name, chunks: res.documents_stored }]);
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

  if (!conversationId) {
    return (
      <div className="chat-main" style={{ justifyContent: 'center', alignItems: 'center', textAlign: 'center' }}>
        <div style={{ color: 'var(--text-dim)', maxWidth: '400px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
          <div className="brand-icon" style={{ width: '56px', height: '56px' }}>
            <Cpu size={32} />
          </div>
          <h3 style={{ color: 'var(--text-main)' }}>No Conversation Selected</h3>
          <p style={{ fontSize: '0.9rem' }}>Select a conversation from the sidebar or start a new chat.</p>
        </div>
      </div>
    );
  }

  return (
    <main className="chat-main">
      {/* Chat header */}
      <div className="chat-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <MessageSquare size={18} style={{ color: '#38bdf8' }} />
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
            <h4 style={{ color: 'var(--text-main)', marginBottom: '8px' }}>Praxis AI Ready</h4>
            <p style={{ fontSize: '0.9rem' }}>
              Ask a question, request deep research, or upload a document via the <strong>+</strong> button.
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
            placeholder={ingesting ? 'Waiting for document to finish uploading...' : 'Ask anything, attach a document (+), or request deep research...'}
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
