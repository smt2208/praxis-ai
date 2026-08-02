import React, { useState } from 'react';
import { Mail, ArrowLeft, CheckCircle, Loader2 } from 'lucide-react';
import { api } from '../../services/api';

/**
 * ForgotPasswordForm
 *
 * Shown inside the AuthModal when the user clicks "Forgot password?".
 * Submits email, shows success message, lets user go back to login.
 */
export const ForgotPasswordForm = ({ onBack }) => {
  const [email, setEmail] = useState('');
  const [emailError, setEmailError] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [serverError, setServerError] = useState('');

  const validateEmail = (val) => {
    if (!val) return 'Email is required';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val)) return 'Please enter a valid email address';
    return '';
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const err = validateEmail(email);
    if (err) { setEmailError(err); return; }

    setLoading(true);
    setServerError('');

    try {
      await api.forgotPassword(email);
      setSubmitted(true);
    } catch (err) {
      setServerError(err.message || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div style={{ textAlign: 'center', padding: '8px 0' }}>
        <CheckCircle size={40} style={{ color: '#34d399', marginBottom: '16px' }} />
        <h3 style={{ margin: '0 0 10px 0', color: 'var(--text-main)', fontSize: '1.05rem', fontWeight: 600 }}>
          Check your inbox
        </h3>
        <p style={{ color: 'var(--text-dim)', fontSize: '0.88rem', lineHeight: 1.6, marginBottom: '24px' }}>
          If <strong style={{ color: 'var(--text-muted)' }}>{email}</strong> is registered, you'll receive a
          password reset link within a few minutes.
        </p>
        <button
          type="button"
          className="btn btn-secondary"
          style={{ width: '100%' }}
          onClick={onBack}
        >
          <ArrowLeft size={16} />
          <span>Back to Sign In</span>
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <p style={{ color: 'var(--text-dim)', fontSize: '0.88rem', lineHeight: 1.6, marginBottom: '20px' }}>
        Enter your account email and we'll send you a link to reset your password.
      </p>

      {serverError && (
        <div className="auth-alert" style={{ marginBottom: '16px' }}>
          <span>{serverError}</span>
        </div>
      )}

      <div className="input-group">
        <label className="input-label" htmlFor="forgot-email">Email Address</label>
        <input
          id="forgot-email"
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (emailError) setEmailError('');
            setServerError('');
          }}
          className={`input-field ${emailError ? 'error' : ''}`}
          disabled={loading}
          autoFocus
        />
        {emailError && <span className="error-text">{emailError}</span>}
      </div>

      <button
        type="submit"
        className="btn btn-primary"
        style={{ width: '100%', marginTop: '12px' }}
        disabled={loading}
      >
        {loading ? (
          <><Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /><span>Sending...</span></>
        ) : (
          <><Mail size={16} /><span>Send Reset Link</span></>
        )}
      </button>

      <button
        type="button"
        onClick={onBack}
        style={{
          background: 'none', border: 'none', color: 'var(--text-dim)',
          fontSize: '0.82rem', cursor: 'pointer', marginTop: '14px',
          display: 'flex', alignItems: 'center', gap: '4px', padding: 0,
        }}
      >
        <ArrowLeft size={13} /> Back to Sign In
      </button>
    </form>
  );
};
