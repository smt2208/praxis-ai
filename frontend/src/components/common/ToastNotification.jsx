import React from 'react';
import { Sparkles, CheckCircle2, LogOut, Info } from 'lucide-react';

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
    <div className="toast-notification" onClick={onClose}>
      {getIcon()}
      <span>{toast.message}</span>
    </div>
  );
};
