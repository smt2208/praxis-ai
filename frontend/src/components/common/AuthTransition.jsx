import React from 'react';

export const AuthTransition = ({ message }) => {
  return (
    <div className="auth-transition-overlay">
      <div className="auth-transition-logo">
        <img src="/logo.png" alt="Praxis" />
        <span>Praxis</span>
      </div>
      <div className="auth-transition-spinner" />
      {message && (
        <p className="auth-transition-message">{message}</p>
      )}
    </div>
  );
};
