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
      background: '#090d16',
      padding: '24px',
    }}>
      <div style={{
        background: '#1e293b',
        border: '1px solid #334155',
        borderRadius: '16px',
        padding: '48px 40px',
        maxWidth: '440px',
        width: '100%',
        textAlign: 'center',
      }}>
        {status === 'loading' && (
          <>
            <Loader2 size={48} style={{ color: '#818cf8', animation: 'spin 1s linear infinite', marginBottom: '16px' }} />
            <h2 style={{ color: '#e2e8f0', marginBottom: '8px' }}>Verifying your email…</h2>
            <p style={{ color: '#64748b', fontSize: '14px' }}>Just a moment.</p>
          </>
        )}

        {status === 'success' && (
          <>
            <CheckCircle size={48} style={{ color: '#34d399', marginBottom: '16px' }} />
            <h2 style={{ color: '#e2e8f0', marginBottom: '8px' }}>Email Verified!</h2>
            <p style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '28px' }}>{message}</p>
            <button
              onClick={onGoToLogin}
              style={{
                padding: '10px 28px',
                background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                fontWeight: 600,
                fontSize: '15px',
                cursor: 'pointer',
              }}
            >
              Go to Login
            </button>
          </>
        )}

        {status === 'error' && (
          <>
            <XCircle size={48} style={{ color: '#f87171', marginBottom: '16px' }} />
            <h2 style={{ color: '#e2e8f0', marginBottom: '8px' }}>Verification Failed</h2>
            <p style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '28px' }}>{message}</p>
            <button
              onClick={onGoToLogin}
              style={{
                padding: '10px 28px',
                background: '#334155',
                color: '#e2e8f0',
                border: 'none',
                borderRadius: '8px',
                fontWeight: 600,
                fontSize: '15px',
                cursor: 'pointer',
              }}
            >
              Back to Login
            </button>
          </>
        )}
      </div>
    </div>
  );
};
