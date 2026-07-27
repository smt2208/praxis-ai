import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';
import { ToastNotification } from '../components/common/ToastNotification';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState('');
  const [toast, setToast] = useState(null);

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  };

  // Check auth state on mount
  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem('access_token');
      if (token) {
        try {
          const userData = await api.getCurrentUser();
          setUser(userData);
        } catch (err) {
          console.error('Failed to restore session:', err);
          logoutLocally();
        }
      }
      setLoading(false);
    };

    initAuth();

    // Event listener for forced logout from API service
    const handleLogoutEvent = () => logoutLocally();
    window.addEventListener('auth:logout', handleLogoutEvent);

    return () => window.removeEventListener('auth:logout', handleLogoutEvent);
  }, []);

  const logoutLocally = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
  };

  const login = async (email, password) => {
    setAuthError('');
    try {
      const data = await api.login(email, password);
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      // Fetch user profile
      const userData = await api.getCurrentUser();
      setUser(userData);
      const name = userData.email ? userData.email.split('@')[0] : 'user';
      showToast(`✨ Welcome back, ${name}! Workspace ready.`, 'login');
      return { success: true };
    } catch (err) {
      const msg = err.message || 'Login failed';
      setAuthError(msg);
      return { success: false, error: msg };
    }
  };

  const register = async (email, password) => {
    setAuthError('');
    try {
      const data = await api.register(email, password);
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      // Fetch user profile
      const userData = await api.getCurrentUser();
      setUser(userData);
      const name = userData.email ? userData.email.split('@')[0] : 'user';
      showToast(`🚀 Welcome to Praxis, ${name}! Your AI workspace is ready.`, 'register');
      return { success: true };
    } catch (err) {
      const msg = err.message || 'Registration failed';
      setAuthError(msg);
      return { success: false, error: msg };
    }
  };

  const logout = async (logoutAll = false) => {
    const refreshToken = localStorage.getItem('refresh_token');
    if (refreshToken) {
      try {
        await api.logout(refreshToken, logoutAll);
      } catch (e) {
        console.warn('Logout endpoint warning:', e);
      }
    }
    logoutLocally();
    showToast('👋 Logged out successfully. See you soon!', 'logout');
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        loading,
        authError,
        setAuthError,
        login,
        register,
        logout,
      }}
    >
      <ToastNotification toast={toast} onClose={() => setToast(null)} />
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
