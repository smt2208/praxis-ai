import React, { useState, useEffect } from 'react';
import { X, Cpu } from 'lucide-react';
import { LoginForm } from './LoginForm';
import { RegisterForm } from './RegisterForm';

export const AuthModal = ({ isOpen, onClose, initialTab = 'login' }) => {
  const [activeTab, setActiveTab] = useState(initialTab);

  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialTab);
    }
  }, [initialTab, isOpen]);

  if (!isOpen) return null;

  return (
    <div className="auth-modal-overlay" onClick={onClose}>
      <div className="auth-modal-container" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close-btn" onClick={onClose} aria-label="Close modal">
          <X size={20} />
        </button>

        <div className="auth-header">
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', color: '#38bdf8', marginBottom: '8px' }}>
            <Cpu size={28} />
          </div>
          <h2>Welcome to Praxis</h2>
          <p>Access your autonomous multi-agent workspace</p>
        </div>

        <div className="auth-tabs">
          <button
            className={`auth-tab ${activeTab === 'login' ? 'active' : ''}`}
            onClick={() => setActiveTab('login')}
          >
            Sign In
          </button>
          <button
            className={`auth-tab ${activeTab === 'register' ? 'active' : ''}`}
            onClick={() => setActiveTab('register')}
          >
            Sign Up
          </button>
        </div>

        {activeTab === 'login' ? (
          <LoginForm onSuccess={onClose} onSwitchToRegister={() => setActiveTab('register')} />
        ) : (
          <RegisterForm onSuccess={onClose} />
        )}
      </div>
    </div>
  );
};
