import React from 'react';
import { Sparkles, CheckCircle2, LogOut, Info, X } from 'lucide-react';

export const ToastNotification = ({ toast, onClose }) => {
  if (!toast) return null;

  const getIcon = () => {
    switch (toast.type) {
      case 'login':
      case 'success':
        return <CheckCircle2 size={18} style={{ color: '#34d399', flexShrink: 0 }} />;
      case 'register':
        return <Sparkles size={18} style={{ color: '#818cf8', flexShrink: 0 }} />;
      case 'logout':
        return <LogOut size={18} style={{ color: '#38bdf8', flexShrink: 0 }} />;
      default:
        return <Info size={18} style={{ color: '#38bdf8', flexShrink: 0 }} />;
    }
  };

  return (
    <div className="toast-notification" onClick={onClose} title="Click to dismiss">
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        {getIcon()}
        <span>{toast.message}</span>
      </div>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
        style={{
          background: 'none',
          border: 'none',
          color: 'var(--text-muted)',
          cursor: 'pointer',
          padding: '2px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginLeft: '8px',
          borderRadius: '50%',
        }}
      >
        <X size={14} />
      </button>
    </div>
  );
};
