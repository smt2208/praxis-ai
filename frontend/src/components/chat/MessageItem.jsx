import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { User, Cpu, BookOpen, Microscope, MessageCircle } from 'lucide-react';

export const MessageItem = ({ message }) => {
  const isUser = message.role === 'user';

  const renderRouteBadge = (route) => {
    if (!route) return null;
    switch (route) {
      case 'knowledge_team':
        return (
          <span className="badge badge-emerald route-badge">
            <BookOpen size={12} />
            <span>Knowledge Team (RAG)</span>
          </span>
        );
      case 'research_team':
        return (
          <span className="badge badge-purple route-badge">
            <Microscope size={12} />
            <span>Deep Research Agent</span>
          </span>
        );
      case 'follow_up':
        return (
          <span className="badge badge-primary route-badge">
            <MessageCircle size={12} />
            <span>Follow-Up Agent</span>
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
        {isUser ? <User size={18} /> : <Cpu size={18} />}
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
            <span className="animate-pulse" style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
              Thinking...
            </span>
          )}
        </div>
        {!isUser && renderRouteBadge(message.route_taken)}
      </div>
    </div>
  );
};
