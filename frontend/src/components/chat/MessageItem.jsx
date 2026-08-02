import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { User, Loader2 } from 'lucide-react';

export const MessageItem = ({ message }) => {
  const isUser = message.role === 'user';
  const hasImages = Array.isArray(message.images) && message.images.length > 0;

  return (
    <div className={`message-bubble ${isUser ? 'user' : 'assistant'}`}>
      <div className="message-avatar">
        {isUser ? <User size={18} /> : <img src="/logo.png" alt="Praxis" style={{ width: 20, height: 20, borderRadius: '4px', objectFit: 'contain' }} />}
      </div>

      <div className="message-content-wrapper">
        {/* Render attached image thumbnails for user messages */}
        {isUser && hasImages && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '6px', justifyContent: 'flex-end' }}>
            {message.images.map((b64, i) => (
              <img
                key={i}
                src={b64}
                alt={`Attached upload ${i + 1}`}
                style={{
                  width: '90px',
                  height: '90px',
                  borderRadius: '10px',
                  objectFit: 'cover',
                  border: '1px solid var(--border-color)',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                }}
              />
            ))}
          </div>
        )}

        <div className="message-content">
          {isUser ? (
            message.content || (hasImages ? <span style={{ fontStyle: 'italic', opacity: 0.8 }}>[Attached image(s)]</span> : '')
          ) : message.content ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 0', color: 'var(--text-muted)' }}>
              <Loader2 size={16} style={{ animation: 'spin 1s linear infinite', color: 'var(--primary)' }} />
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
