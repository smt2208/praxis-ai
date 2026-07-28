import React from 'react';
import { MessageSquarePlus, MessageSquare, LogOut, Cpu, ShieldAlert, Trash2, X } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export const Sidebar = ({
  conversations,
  activeConvId,
  onSelectConv,
  onNewConv,
  onDeleteConv,
  isOpen,
  onClose,
}) => {
  const { user, logout } = useAuth();

  const getInitials = (email) => {
    if (!email) return 'U';
    return email.charAt(0).toUpperCase();
  };

  return (
    <>
      <div className={`sidebar-overlay ${isOpen ? 'open' : ''}`} onClick={onClose} />
      <aside className={`chat-sidebar ${isOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontWeight: 700, fontSize: '1.1rem' }}>
            <img src="/logo.png" alt="Praxis Logo" style={{ width: 26, height: 26, borderRadius: '6px', objectFit: 'contain' }} />
            <span>Praxis</span>
          </div>
          <button className="sidebar-close-btn" onClick={onClose} title="Close sidebar">
            <X size={20} />
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
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden', flex: 1 }}>
                <MessageSquare size={16} style={{ flexShrink: 0 }} />
                <span className="conv-title">{conv.title || 'Untitled'}</span>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); onDeleteConv(conv.conversation_id); }}
                title="Delete conversation"
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--text-dim)',
                  padding: '2px 4px',
                  borderRadius: '4px',
                  flexShrink: 0,
                  opacity: 0.5,
                  transition: 'opacity 0.2s, color 0.2s',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.color = '#f87171'; }}
                onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.5'; e.currentTarget.style.color = 'var(--text-dim)'; }}
              >
                <Trash2 size={14} />
              </button>
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

        <button
          className="btn btn-secondary"
          style={{ width: '100%', padding: '9px', fontSize: '0.85rem' }}
          onClick={() => logout(false)}
          title="Sign Out"
        >
          <LogOut size={16} />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
    </>
  );
};
