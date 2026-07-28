import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { User, Loader2 } from 'lucide-react';

export const MessageItem = ({ message }) => {
  const isUser = message.role === 'user';

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
                {message.status_message || 'Thinking...'}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

