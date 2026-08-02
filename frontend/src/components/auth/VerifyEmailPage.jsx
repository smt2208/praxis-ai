import React, { useEffect, useState } from 'react';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { api } from '../../services/api';

/**
 * VerifyEmailPage
 *
 * Shown when the user clicks the verification link in their email.
 * Reads the ?token= query param and POSTs it to /api/v1/auth/verify-email.
 * Displays a success or error state accordingly.
 */
export const VerifyEmailPage = ({ onGoToLogin }) => {
  const [status, setStatus] = useState('loading'); // 'loading' | 'success' | 'error'
  const [message, setMessage] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');

    if (!token) {
      setStatus('error');
      setMessage('No verification token found in the link. Please use the link from your email.');
      return;
    }

    api.verifyEmail(token)
      .then(() => {
        setStatus('success');
        setMessage('Your email has been verified! You can now log in.');
      })
      .catch((err) => {
        setStatus('error');
        setMessage(err.message || 'Verification failed. The link may be invalid or already used.');
      });
  }, []);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      background: 'var(--bg-base)',
      padding: '24px',
    }}>
      <div style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border-color)',
        borderRadius: 'var(--radius-xl)',
        padding: '48px 40px',
        maxWidth: '440px',
        width: '100%',
        textAlign: 'center',
        boxShadow: '0 20px 50px rgba(0,0,0,0.2)',
      }}>
        {status === 'loading' && (
          <>
            <Loader2 size={48} style={{ color: 'var(--primary)', animation: 'spin 1s linear infinite', marginBottom: '16px' }} />
            <h2 style={{ color: 'var(--text-main)', marginBottom: '8px' }}>Verifying your email…</h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '14px' }}>Just a moment.</p>
          </>
        )}

        {status === 'success' && (
          <>
            <CheckCircle size={48} style={{ color: 'var(--accent-emerald)', marginBottom: '16px' }} />
            <h2 style={{ color: 'var(--text-main)', marginBottom: '8px' }}>Email Verified!</h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginBottom: '28px' }}>{message}</p>
            <button
              onClick={onGoToLogin}
              className="btn btn-primary"
              style={{ padding: '10px 28px' }}
            >
              Go to Login
            </button>
          </>
        )}

        {status === 'error' && (
          <>
            <XCircle size={48} style={{ color: 'var(--accent-rose)', marginBottom: '16px' }} />
            <h2 style={{ color: 'var(--text-main)', marginBottom: '8px' }}>Verification Failed</h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginBottom: '28px' }}>{message}</p>
            <button
              onClick={onGoToLogin}
              className="btn btn-secondary"
              style={{ padding: '10px 28px' }}
            >
              Go to Login
            </button>
          </>
        )}
      </div>
    </div>
  );
};
