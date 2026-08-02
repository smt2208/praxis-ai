import React, { useState, useEffect } from 'react';
import { Lock, CheckCircle, AlertCircle, Loader2, Eye, EyeOff } from 'lucide-react';
import { api } from '../../services/api';

/**
 * ResetPasswordPage
 *
 * Full-page component shown at /reset-password?token=...
 * Validates the token, lets the user set a new password, then redirects.
 */
export const ResetPasswordPage = ({ onGoToLogin }) => {
  const [token, setToken] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [serverError, setServerError] = useState('');

  // Extract token from URL on mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const t = params.get('token') || '';
    setToken(t);
    if (!t) {
      setServerError('No reset token found. Please use the link from your email.');
    }
  }, []);

  const validate = () => {
    const errs = {};
    if (!password) {
      errs.password = 'Password is required';
    } else if (password.length < 8) {
      errs.password = 'Password must be at least 8 characters';
    }
    if (!confirmPassword) {
      errs.confirmPassword = 'Please confirm your password';
    } else if (password !== confirmPassword) {
      errs.confirmPassword = 'Passwords do not match';
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;

    setLoading(true);
    setServerError('');

    try {
      await api.resetPassword(token, password);
      setSuccess(true);
    } catch (err) {
      setServerError(err.message || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#090d16',
      padding: '24px 16px',
      fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    }}>
      <div style={{
        width: '100%',
        maxWidth: '420px',
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: '16px',
        padding: '40px 36px',
        backdropFilter: 'blur(12px)',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <div style={{ fontWeight: 700, fontSize: '22px', color: '#818cf8', letterSpacing: '-0.02em', marginBottom: '6px' }}>
            Praxis
          </div>
          <h1 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 600, color: '#f1f5f9' }}>
            {success ? 'Password Reset!' : 'Create New Password'}
          </h1>
        </div>

        {success ? (
          <div style={{ textAlign: 'center' }}>
            <CheckCircle size={44} style={{ color: '#34d399', marginBottom: '16px' }} />
            <p style={{ color: '#94a3b8', fontSize: '0.9rem', lineHeight: 1.6, marginBottom: '24px' }}>
              Your password has been reset successfully. You can now sign in with your new password.
            </p>
            <button
              onClick={onGoToLogin}
              className="btn btn-primary"
              style={{ width: '100%' }}
            >
              Sign In Now
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} noValidate>
            {serverError && (
              <div className="auth-alert" style={{ marginBottom: '18px', display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '1px' }} />
                <span>{serverError}</span>
              </div>
            )}

            <div className="input-group">
              <label className="input-label" htmlFor="new-password">New Password</label>
              <div style={{ position: 'relative' }}>
                <input
                  id="new-password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Minimum 8 characters"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (errors.password) setErrors(p => ({ ...p, password: '' }));
                  }}
                  className={`input-field ${errors.password ? 'error' : ''}`}
                  disabled={loading || !token}
                  style={{ paddingRight: '42px' }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(p => !p)}
                  style={{
                    position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)',
                    background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-dim)', padding: 0,
                  }}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {errors.password && <span className="error-text">{errors.password}</span>}
            </div>

            <div className="input-group">
              <label className="input-label" htmlFor="confirm-password">Confirm Password</label>
              <input
                id="confirm-password"
                type={showPassword ? 'text' : 'password'}
                placeholder="Re-enter your new password"
                value={confirmPassword}
                onChange={(e) => {
                  setConfirmPassword(e.target.value);
                  if (errors.confirmPassword) setErrors(p => ({ ...p, confirmPassword: '' }));
                }}
                className={`input-field ${errors.confirmPassword ? 'error' : ''}`}
                disabled={loading || !token}
              />
              {errors.confirmPassword && <span className="error-text">{errors.confirmPassword}</span>}
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', marginTop: '12px' }}
              disabled={loading || !token}
            >
              {loading ? (
                <><Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /><span>Saving...</span></>
              ) : (
                <><Lock size={16} /><span>Reset Password</span></>
              )}
            </button>

            <button
              type="button"
              onClick={onGoToLogin}
              style={{
                background: 'none', border: 'none', color: 'var(--text-dim)',
                fontSize: '0.82rem', cursor: 'pointer', marginTop: '14px',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: '100%', padding: 0,
              }}
            >
              Back to Sign In
            </button>
          </form>
        )}
      </div>
    </div>
  );
};
