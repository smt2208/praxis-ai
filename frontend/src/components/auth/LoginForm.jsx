import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { LogIn, Mail, Lock } from 'lucide-react';

export const LoginForm = ({ onSuccess, onSwitchToRegister }) => {
  const { login } = useAuth();
  const [formData, setFormData] = useState({ email: '', password: '' });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [serverError, setServerError] = useState('');

  const validate = () => {
    const errs = {};
    if (!formData.email) {
      errs.email = 'Email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      errs.email = 'Please enter a valid email address';
    }

    if (!formData.password) {
      errs.password = 'Password is required';
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    // Clear validation error when user types
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

    const res = await login(formData.email, formData.password);
    setLoading(false);

    if (res.success) {
      if (onSuccess) onSuccess();
    } else {
      setServerError(res.error);
    }
  };

  return (
    <form onSubmit={handleSubmit} noValidate>
      {serverError && (
        <div className="auth-alert" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '6px' }}>
          <span>{serverError}</span>
          {onSwitchToRegister && (
            <button
              type="button"
              onClick={onSwitchToRegister}
              style={{
                background: 'none',
                border: 'none',
                color: '#38bdf8',
                fontSize: '0.8rem',
                fontWeight: 600,
                textDecoration: 'underline',
                cursor: 'pointer',
                padding: 0,
              }}
            >
              Don't have an account yet? Create one here →
            </button>
          )}
        </div>
      )}

      <div className="input-group">
        <label className="input-label" htmlFor="login-email">Email Address</label>
        <div style={{ position: 'relative' }}>
          <input
            id="login-email"
            type="email"
            name="email"
            placeholder="you@example.com"
            value={formData.email}
            onChange={handleChange}
            className={`input-field ${errors.email ? 'error' : ''}`}
            disabled={loading}
          />
        </div>
        {errors.email && <span className="error-text">{errors.email}</span>}
      </div>

      <div className="input-group">
        <label className="input-label" htmlFor="login-password">Password</label>
        <div style={{ position: 'relative' }}>
          <input
            id="login-password"
            type="password"
            name="password"
            placeholder="••••••••"
            value={formData.password}
            onChange={handleChange}
            className={`input-field ${errors.password ? 'error' : ''}`}
            disabled={loading}
          />
        </div>
        {errors.password && <span className="error-text">{errors.password}</span>}
      </div>

      <button
        type="submit"
        className="btn btn-primary"
        style={{ width: '100%', marginTop: '12px' }}
        disabled={loading}
      >
        {loading ? (
          <span>Authenticating...</span>
        ) : (
          <>
            <LogIn size={18} />
            <span>Sign In</span>
          </>
        )}
      </button>
    </form>
  );
};
