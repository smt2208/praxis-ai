import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { LoginForm } from './LoginForm';
import { RegisterForm } from './RegisterForm';
import { ForgotPasswordForm } from './ForgotPasswordForm';

export const AuthModal = ({ isOpen, onClose, initialTab = 'login' }) => {
  // activeTab: 'login' | 'register' | 'forgot'
  const [activeTab, setActiveTab] = useState(initialTab);

  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialTab);
    }
  }, [initialTab, isOpen]);

  if (!isOpen) return null;

  const showTabs = activeTab !== 'forgot';

  return (
    <div className="auth-modal-overlay" onClick={onClose}>
      <div className="auth-modal-container" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close-btn" onClick={onClose} aria-label="Close modal">
          <X size={20} />
        </button>

        <div className="auth-header">
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', color: '#38bdf8', marginBottom: '8px' }}>
            <img src="/logo.png" alt="Praxis Logo" style={{ width: 36, height: 36, borderRadius: '8px', objectFit: 'contain' }} />
          </div>
          <h2>
            {activeTab === 'forgot' ? 'Forgot Password' : 'Welcome to Praxis'}
          </h2>
          {showTabs && <p>Access your autonomous multi-agent workspace</p>}
        </div>

        {/* Tabs — hidden on the forgot view */}
        {showTabs && (
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
        )}

        {activeTab === 'login' && (
          <LoginForm
            onSuccess={onClose}
            onSwitchToRegister={() => setActiveTab('register')}
            onForgotPassword={() => setActiveTab('forgot')}
          />
        )}
        {activeTab === 'register' && (
          <RegisterForm onSuccess={onClose} />
        )}
        {activeTab === 'forgot' && (
          <ForgotPasswordForm onBack={() => setActiveTab('login')} />
        )}
      </div>
    </div>
  );
};
