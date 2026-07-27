import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { User, Cpu, BookOpen, Microscope, MessageCircle, Sparkles, Loader2 } from 'lucide-react';

export const MessageItem = ({ message }) => {
  const isUser = message.role === 'user';

  const renderRouteBadge = (route) => {
    if (!route || route === 'ceo') return null;
    switch (route) {
      case 'knowledge_team':
      case 'knowledge':
        return (
          <span className="badge badge-emerald route-badge">
            <BookOpen size={12} />
            <span>Knowledge Base</span>
          </span>
        );
      case 'research_team':
      case 'research':
        return (
          <span className="badge badge-purple route-badge">
            <Microscope size={12} />
            <span>Deep Research</span>
          </span>
        );
      case 'follow_up':
      case 'chat':
        return (
          <span className="badge badge-primary route-badge">
            <MessageCircle size={12} />
            <span>Conversational</span>
          </span>
        );
      case 'general':
        return (
          <span className="badge badge-primary route-badge">
            <Sparkles size={12} />
            <span>Web Search & Synthesis</span>
          </span>
        );
      default:
        return (
          <span className="badge badge-primary route-badge">
            <Cpu size={12} />
            <span>{route}</span>
          </span>
        );
    }
  };

  return (
    <div className={`message-bubble ${isUser ? 'user' : 'assistant'}`}>
      <div className="message-avatar">
        {isUser ? <User size={18} /> : <img src="/logo.png" alt="Praxis AI" style={{ width: 20, height: 20, borderRadius: '4px', objectFit: 'contain' }} />}
      </div>

      <div className="message-content-wrapper">
        <div className="message-content">
          {isUser ? (
            message.content
          ) : message.content ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 0', color: 'var(--text-muted)' }}>
              <Loader2 size={16} style={{ animation: 'spin 1s linear infinite', color: '#818cf8' }} />
              <span style={{ fontSize: '0.88rem', fontWeight: 500 }}>
                {message.status_message || 'Processing request...'}
              </span>
            </div>
          )}
        </div>
        {!isUser && message.content && renderRouteBadge(message.route_taken)}
      </div>
    </div>
  );
};

