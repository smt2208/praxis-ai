import React from 'react';
import { MessageSquarePlus, MessageSquare, LogOut, Cpu, Home, ShieldAlert } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export const Sidebar = ({
  conversations,
  activeConvId,
  onSelectConv,
  onNewConv,
  onGoHome,
}) => {
  const { user, logout } = useAuth();

  const getInitials = (email) => {
    if (!email) return 'U';
    return email.charAt(0).toUpperCase();
  };

  return (
    <aside className="chat-sidebar">
      <div className="sidebar-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontWeight: 700, fontSize: '1.1rem' }}>
          <Cpu size={22} style={{ color: '#38bdf8' }} />
          <span>Praxis AI</span>
        </div>
        <button
          className="btn btn-secondary"
          style={{ padding: '6px 10px', fontSize: '0.8rem' }}
          onClick={onGoHome}
          title="Return to Landing Page"
        >
          <Home size={16} />
        </button>
      </div>

      <button className="btn btn-primary new-chat-btn" onClick={onNewConv}>
        <MessageSquarePlus size={18} />
        <span>New Conversation</span>
      </button>


      <div style={{ padding: '8px 16px 4px', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase' }}>
        Recent Chats
      </div>

      <div className="conversations-list">
        {conversations.length === 0 ? (
          <div style={{ padding: '16px', color: 'var(--text-dim)', fontSize: '0.85rem', textAlign: 'center' }}>
            No conversations yet. Click "New Conversation" to start.
          </div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.conversation_id}
              className={`conversation-item ${conv.conversation_id === activeConvId ? 'active' : ''}`}
              onClick={() => onSelectConv(conv.conversation_id)}
            >
              <MessageSquare size={16} style={{ flexShrink: 0 }} />
              <span className="conv-title">{conv.title || 'Untitled Session'}</span>
            </div>
          ))
        )}
      </div>

      <div className="sidebar-footer">
        <div className="user-profile">
          <div className="user-avatar">{getInitials(user?.email)}</div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span className="user-email">{user?.email || 'User'}</span>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>Authenticated</span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            className="btn btn-secondary"
            style={{ flex: 1, padding: '8px', fontSize: '0.8rem' }}
            onClick={() => logout(false)}
            title="Log out current session"
          >
            <LogOut size={16} />
            <span>Sign Out</span>
          </button>
          <button
            className="btn btn-danger"
            style={{ padding: '8px', fontSize: '0.8rem' }}
            onClick={() => logout(true)}
            title="Log out ALL devices"
          >
            <ShieldAlert size={16} />
          </button>
        </div>
      </div>
    </aside>
  );
};
