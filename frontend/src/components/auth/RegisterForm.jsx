import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { UserPlus, Mail } from 'lucide-react';

export const RegisterForm = ({ onSuccess }) => {
  const { register } = useAuth();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [serverError, setServerError] = useState('');
  const [needsVerification, setNeedsVerification] = useState(false);
  const [registeredEmail, setRegisteredEmail] = useState('');

  const validate = () => {
    const errs = {};
    if (!formData.email) {
      errs.email = 'Email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      errs.email = 'Please enter a valid email address';
    }

    if (!formData.password) {
      errs.password = 'Password is required';
    } else if (formData.password.length < 8) {
      errs.password = 'Password must be at least 8 characters long';
    }

    if (formData.confirmPassword !== formData.password) {
      errs.confirmPassword = 'Passwords do not match';
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: '' }));
    }
    setServerError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;

    setLoading(true);
    setServerError('');

    const res = await register(formData.email, formData.password);
    setLoading(false);

    if (res.success) {
      if (res.needs_verification) {
        // Show "check your inbox" state instead of logging in
        setRegisteredEmail(formData.email);
        setNeedsVerification(true);
      } else {
        if (onSuccess) onSuccess();
      }
    } else {
      setServerError(res.error);
    }
  };

  // ── Check your inbox state ──
  if (needsVerification) {
    return (
      <div style={{ textAlign: 'center', padding: '16px 0' }}>
        <div style={{
          width: '64px',
          height: '64px',
          background: 'rgba(99, 102, 241, 0.15)',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 20px',
        }}>
          <Mail size={28} style={{ color: '#818cf8' }} />
        </div>
        <h3 style={{ color: '#e2e8f0', marginBottom: '10px', fontSize: '18px' }}>
          Check your inbox!
        </h3>
        <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: 1.6, marginBottom: '6px' }}>
          We sent a verification link to:
        </p>
        <p style={{ color: '#818cf8', fontWeight: 600, fontSize: '15px', marginBottom: '20px' }}>
          {registeredEmail}
        </p>
        <p style={{ color: '#64748b', fontSize: '13px', lineHeight: 1.6 }}>
          Click the link in the email to activate your account.<br />
          The link expires in 24 hours.
        </p>
      </div>
    );
  }

  // ── Registration form ──
  return (
    <form onSubmit={handleSubmit} noValidate>
      {serverError && (
        <div className="auth-alert">
          <span>{serverError}</span>
        </div>
      )}

      <div className="input-group">
        <label className="input-label" htmlFor="reg-email">Email Address</label>
        <input
          id="reg-email"
          type="email"
          name="email"
          placeholder="you@example.com"
          value={formData.email}
          onChange={handleChange}
          className={`input-field ${errors.email ? 'error' : ''}`}
          disabled={loading}
        />
        {errors.email && <span className="error-text">{errors.email}</span>}
      </div>

      <div className="input-group">
        <label className="input-label" htmlFor="reg-password">Password (Min 8 chars)</label>
        <input
          id="reg-password"
          type="password"
          name="password"
          placeholder="••••••••"
          value={formData.password}
          onChange={handleChange}
          className={`input-field ${errors.password ? 'error' : ''}`}
          disabled={loading}
        />
        {errors.password && <span className="error-text">{errors.password}</span>}
      </div>

      <div className="input-group">
        <label className="input-label" htmlFor="reg-confirm">Confirm Password</label>
        <input
          id="reg-confirm"
          type="password"
          name="confirmPassword"
          placeholder="••••••••"
          value={formData.confirmPassword}
          onChange={handleChange}
          className={`input-field ${errors.confirmPassword ? 'error' : ''}`}
          disabled={loading}
        />
        {errors.confirmPassword && <span className="error-text">{errors.confirmPassword}</span>}
      </div>

      <button
        type="submit"
        className="btn btn-primary"
        style={{ width: '100%', marginTop: '12px' }}
        disabled={loading}
      >
        {loading ? (
          <span>Creating account...</span>
        ) : (
          <>
            <UserPlus size={18} />
            <span>Create Account</span>
          </>
        )}
      </button>
    </form>
  );
};
