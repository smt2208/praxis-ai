import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Send, Square, Cpu, Sparkles, MessageSquare, Plus, Loader2, FileText, X, Menu, RotateCcw, Image as ImageIcon, FileUp, PanelLeft } from 'lucide-react';
import { MessageItem } from './MessageItem';
import { api } from '../../services/api';
import { useChatStream } from '../../hooks/useChatStream';
import { useFileUpload } from '../../hooks/useFileUpload';

export const ChatWindow = ({ conversationId, activeTitle, onRefreshConversations, onSelectActiveConv, onToggleSidebar, sidebarOpen }) => {
  const [inputMessage, setInputMessage] = useState('');
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Multimodal image state
  const [selectedImages, setSelectedImages] = useState([]); // array of base64 data URIs
  const [attachMenuOpen, setAttachMenuOpen] = useState(false);

  const messagesEndRef       = useRef(null);
  const messagesContainerRef  = useRef(null);
  const textareaRef          = useRef(null);
  const imageInputRef         = useRef(null);
  const attachMenuRef        = useRef(null);

  // Close attach popover menu on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (attachMenuRef.current && !attachMenuRef.current.contains(e.target)) {
        setAttachMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // ── Auto-scroll helpers ─────────────────────────────────────────────────

  const isNearBottom = useCallback(() => {
    const el = messagesContainerRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 150;
  }, []);

  const scrollToBottom = useCallback(() => {
    if (isNearBottom()) messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [isNearBottom]);

  // ── Textarea auto-grow ──────────────────────────────────────────────────

  const adjustTextareaHeight = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px';
  }, []);

  const resetTextareaHeight = useCallback(() => {
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  }, []);

  // ── Chat stream hook ────────────────────────────────────────────────────

  const {
    messages, setMessages,
    sending, error, setError,
    lastFailedMessage,
    isSendingRef, setConversationId,
    ensureActiveConversation,
    doSend, handleStop, handleRetry,
  } = useChatStream({
    scrollToBottom,
    onConversationCreated: onSelectActiveConv,
    onRefreshConversations,
  });

  // ── File upload hook ────────────────────────────────────────────────────

  useEffect(() => {
    setConversationId(conversationId);
  }, [conversationId, setConversationId]);

  const {
    ingesting, uploadingFileName,
    activeFiles, setActiveFiles,
    fileInputRef,
    handleQuickFileSelect, removeFile,
  } = useFileUpload({ ensureActiveConversation, setError, onRefreshConversations });

  // ── Image selection handler ─────────────────────────────────────────────

  const handleImageSelect = (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;

    setAttachMenuOpen(false);

    files.slice(0, 5 - selectedImages.length).forEach((file) => {
      if (!file.type.startsWith('image/')) return;
      const reader = new FileReader();
      reader.onload = (event) => {
        const b64 = event.target.result;
        setSelectedImages((prev) => (prev.length < 5 ? [...prev, b64] : prev));
      };
      reader.readAsDataURL(file);
    });

    if (e.target) e.target.value = '';
  };

  const removeImage = (index) => {
    setSelectedImages((prev) => prev.filter((_, i) => i !== index));
  };

  // ── Load history when conversation changes ──────────────────────────────

  useEffect(() => {
    setError(null);

    if (isSendingRef.current) return;   // preserve optimistic state mid-send

    if (!conversationId) {
      setMessages([]);
      setActiveFiles([]);
      setSelectedImages([]);
      setLoadingHistory(false);
      return;
    }

    let cancelled = false;
    const fetchData = async () => {
      setLoadingHistory(true);
      try {
        const [history, docs] = await Promise.all([
          api.getMessages(conversationId),
          api.getDocuments(conversationId).catch(() => []),
        ]);
        if (cancelled) return;
        setMessages(history);
        if (Array.isArray(docs)) setActiveFiles(docs.map((f) => ({ name: f })));
      } catch {
        if (!cancelled) setError('Failed to load message history.');
      } finally {
        if (!cancelled) setLoadingHistory(false);
      }
    };
    fetchData();

    return () => { cancelled = true; };
  }, [conversationId]);   // eslint-disable-line react-hooks/exhaustive-deps

  // Scroll to bottom after history loads
  useEffect(() => {
    if (!loadingHistory && messages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
    }
  }, [loadingHistory, conversationId]);

  // ── Send ────────────────────────────────────────────────────────────────

  const handleSend = async (e) => {
    e.preventDefault();
    if ((!inputMessage.trim() && selectedImages.length === 0) || sending) return;
    const text = inputMessage.trim();
    const imgs = [...selectedImages];

    setInputMessage('');
    setSelectedImages([]);
    resetTextareaHeight();
    setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
    await doSend(text, imgs);
  };

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <main className="chat-main">

      {/* ── Header ── */}
      <div className="chat-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            className="sidebar-toggle-btn"
            onClick={onToggleSidebar}
            title={sidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
          >
            <PanelLeft size={19} />
          </button>
          <MessageSquare size={18} style={{ color: 'var(--primary)' }} />
          <span style={{ fontWeight: 600, fontSize: '0.95rem', color: 'var(--text-main)' }}>
            {activeTitle || 'New Conversation'}
          </span>
        </div>
      </div>

      {/* ── Messages ── */}
      <div className="messages-container" ref={messagesContainerRef}>

        {loadingHistory ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '60px 20px', gap: '16px' }}>
            <Loader2 size={28} style={{ animation: 'spin 1s linear infinite', color: 'var(--primary)' }} />
            <span style={{ color: 'var(--text-dim)', fontSize: '0.9rem', fontWeight: 500 }}>Loading conversation...</span>
          </div>

        ) : messages.length === 0 ? (
          <div style={{ textAlign: 'center', margin: 'auto', color: 'var(--text-dim)', maxWidth: '440px' }}>
            <Sparkles size={36} style={{ color: 'var(--primary)', marginBottom: '12px' }} />
            <h4 style={{ color: 'var(--text-main)', marginBottom: '8px' }}>Praxis Ready</h4>
            <p style={{ fontSize: '0.9rem' }}>Ask a question, upload a document, or share images for visual analysis.</p>
          </div>

        ) : (
          messages.map((msg, idx) => <MessageItem key={idx} message={msg} />)
        )}

        {/* Thinking indicator while waiting for first token */}
        {sending && (messages.length === 0 || messages[messages.length - 1]?.role !== 'assistant') && (
          <div className="message-bubble assistant">
            <div className="message-avatar"><Cpu size={18} className="animate-pulse" /></div>
            <div className="message-content" style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="animate-pulse">Thinking...</span>
            </div>
          </div>
        )}

        {/* Error + Retry */}
        {error && (
          <div className="auth-alert" style={{ margin: '8px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
            <span>{error}</span>
            {lastFailedMessage && !sending && (
              <button
                onClick={handleRetry}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: '6px',
                  background: 'var(--primary-soft)', border: '1px solid var(--border-glow)',
                  color: 'var(--primary)', padding: '6px 14px', borderRadius: '8px',
                  fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer',
                  transition: 'all 0.2s ease', flexShrink: 0,
                }}
              >
                <RotateCcw size={14} /> Retry
              </button>
            )}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ── Input area ── */}
      <div className="chat-input-area">

        {/* Upload progress indicator */}
        {ingesting && uploadingFileName && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            fontSize: '0.82rem', color: 'var(--accent-sky)',
            background: 'rgba(56, 189, 248, 0.12)', border: '1px solid rgba(56, 189, 248, 0.25)',
            padding: '6px 12px', borderRadius: '8px', marginBottom: '8px',
          }}>
            <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
            <span>Uploading <strong>{uploadingFileName}</strong>...</span>
          </div>
        )}

        {/* Active document pills */}
        {activeFiles.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '8px' }}>
            {activeFiles.map((f, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                fontSize: '0.78rem', color: 'var(--accent-emerald)',
                background: 'rgba(52, 211, 153, 0.12)', border: '1px solid rgba(52, 211, 153, 0.25)',
                padding: '4px 10px', borderRadius: '20px',
              }}>
                <FileText size={12} />
                <span>{f.name}</span>
                <button onClick={() => removeFile(i)} title="Remove from view"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-dim)', padding: '0 2px', lineHeight: 1 }}>
                  <X size={11} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Selected Image Thumbnails Strip */}
        {selectedImages.length > 0 && (
          <div style={{ display: 'flex', gap: '8px', marginBottom: '8px', overflowX: 'auto', paddingBottom: '4px' }}>
            {selectedImages.map((b64, idx) => (
              <div key={idx} style={{ position: 'relative', width: '56px', height: '56px', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--border-color)', flexShrink: 0 }}>
                <img src={b64} alt={`Upload ${idx + 1}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                <button
                  type="button"
                  onClick={() => removeImage(idx)}
                  style={{
                    position: 'absolute', top: '2px', right: '2px',
                    background: 'rgba(0, 0, 0, 0.65)', color: '#ffffff',
                    border: 'none', borderRadius: '50%', width: '18px', height: '18px',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    cursor: 'pointer',
                  }}
                  title="Remove image"
                >
                  <X size={11} />
                </button>
              </div>
            ))}
          </div>
        )}

        <form onSubmit={handleSend} className="chat-input-box" style={{ position: 'relative' }}>

          {/* Hidden inputs */}
          <input type="file" ref={fileInputRef} onChange={handleQuickFileSelect}
            style={{ display: 'none' }} accept=".pdf,.docx,.pptx,.txt,.md" />
          <input type="file" ref={imageInputRef} onChange={handleImageSelect}
            style={{ display: 'none' }} accept="image/jpeg,image/png,image/webp,image/gif" multiple />

          {/* Attach Menu Button & Popover */}
          <div ref={attachMenuRef} style={{ position: 'relative' }}>
            <button type="button" className="attach-btn"
              onClick={() => setAttachMenuOpen((prev) => !prev)}
              title="Attach document or upload images"
              disabled={ingesting || sending}
              style={{
                background: attachMenuOpen ? 'var(--primary-soft)' : 'var(--bg-card)',
                border: '1px solid var(--border-color)', borderRadius: '50%',
                width: '36px', height: '36px', display: 'flex', alignItems: 'center',
                justifyContent: 'center', color: attachMenuOpen ? 'var(--primary)' : 'var(--text-muted)',
                cursor: 'pointer', transition: 'all 0.2s ease', flexShrink: 0,
              }}>
              {ingesting ? <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} /> : <Plus size={20} />}
            </button>

            {/* Popover Menu */}
            {attachMenuOpen && (
              <div
                style={{
                  position: 'absolute',
                  bottom: '48px',
                  left: '0',
                  zIndex: 200,
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-md)',
                  padding: '6px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '2px',
                  boxShadow: '0 10px 30px rgba(0,0,0,0.25)',
                  minWidth: '175px',
                  animation: 'fadeInUp 0.18s ease-out',
                }}
              >
                <button
                  type="button"
                  onClick={() => { setAttachMenuOpen(false); fileInputRef.current?.click(); }}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '10px',
                    padding: '8px 12px', border: 'none', background: 'none',
                    color: 'var(--text-main)', borderRadius: 'var(--radius-sm)',
                    fontSize: '0.86rem', cursor: 'pointer', fontWeight: 500,
                    textAlign: 'left', width: '100%',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-card-hover)'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'none'}
                >
                  <FileUp size={16} style={{ color: 'var(--accent-emerald)' }} />
                  <span>Attach Document</span>
                </button>

                <button
                  type="button"
                  onClick={() => { setAttachMenuOpen(false); imageInputRef.current?.click(); }}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '10px',
                    padding: '8px 12px', border: 'none', background: 'none',
                    color: 'var(--text-main)', borderRadius: 'var(--radius-sm)',
                    fontSize: '0.86rem', cursor: 'pointer', fontWeight: 500,
                    textAlign: 'left', width: '100%',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-card-hover)'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'none'}
                >
                  <ImageIcon size={16} style={{ color: 'var(--primary)' }} />
                  <span>Upload Image</span>
                </button>
              </div>
            )}
          </div>

          {/* Auto-growing textarea */}
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            placeholder={ingesting ? 'Waiting for document to finish uploading...' : 'Ask me anything or analyze images...'}
            value={inputMessage}
            onChange={(e) => { setInputMessage(e.target.value); adjustTextareaHeight(); }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(e); }
            }}
            rows={1}
            disabled={ingesting}
          />

          {/* Stop / Send button */}
          {sending ? (
            <button type="button" className="send-btn stop-btn" onClick={handleStop} title="Stop generating">
              <Square size={14} fill="white" />
            </button>
          ) : (
            <button type="submit" className="send-btn"
              disabled={(!inputMessage.trim() && selectedImages.length === 0) || ingesting} title="Send Message">
              <Send size={18} />
            </button>
          )}
        </form>
      </div>
    </main>
  );
};
