// Uses Vercel Proxy Rewrite in production when VITE_API_BASE_URL is empty ('') to eliminate Mixed Content & CORS errors
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');

/**
 * Custom fetch wrapper that automatically injects JWT Bearer header
 * and handles error responses.
 */
async function request(endpoint, options = {}) {
  const accessToken = localStorage.getItem('access_token');

  const headers = {
    ...options.headers,
  };

  if (accessToken && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }

  // Set default Content-Type to JSON unless sending FormData
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const config = {
    ...options,
    headers,
  };

  let response = await fetch(`${API_BASE_URL}${endpoint}`, config);

  // If token is expired (401), attempt to refresh once
  if (response.status === 401 && endpoint !== '/api/v1/auth/login' && endpoint !== '/api/v1/auth/register') {
    const refreshToken = localStorage.getItem('refresh_token');
    if (refreshToken) {
      const refreshed = await refreshTokenPair(refreshToken);
      if (refreshed) {
        // Retry original request with new access token
        headers['Authorization'] = `Bearer ${localStorage.getItem('access_token')}`;
        response = await fetch(`${API_BASE_URL}${endpoint}`, { ...config, headers });
      } else {
        // Refresh token failed -> trigger logout event
        window.dispatchEvent(new Event('auth:logout'));
      }
    }
  }

  // Handle errors
  if (!response.ok) {
    let errorMessage = `Request failed with status ${response.status}`;
    try {
      const errorData = await response.json();
      if (errorData.detail) {
        errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : JSON.stringify(errorData.detail);
      }
    } catch (e) {
      // Ignore json parse error
    }
    throw new Error(errorMessage);
  }

  // 204 No Content
  if (response.status === 204) {
    return null;
  }

  return response.json();
}

/**
 * Helper to exchange refresh token for a new access token
 */
async function refreshTokenPair(refreshToken) {
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!res.ok) return false;

    const data = await res.json();
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

// Export API endpoints
export const api = {
  // Auth
  register: (email, password) => request('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  }),

  login: (email, password) => request('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  }),

  logout: (refreshToken, logoutAllDevices = false) => request('/api/v1/auth/logout', {
    method: 'POST',
    body: JSON.stringify({ refresh_token: refreshToken, logout_all_devices: logoutAllDevices }),
  }),

  getCurrentUser: () => request('/api/v1/auth/me', {
    method: 'GET',
  }),

  // Conversations
  getConversations: () => request('/api/v1/conversations', {
    method: 'GET',
  }),

  createConversation: (title = 'New Conversation') => request('/api/v1/conversations', {
    method: 'POST',
    body: JSON.stringify({ title }),
  }),

  getMessages: (conversationId) => request(`/api/v1/conversations/${conversationId}/messages`, {
    method: 'GET',
  }),

  // Chat
  sendMessage: (conversationId, message) => request('/api/v1/chat', {
    method: 'POST',
    body: JSON.stringify({ conversation_id: conversationId, message }),
  }),

  // Ingestion
  ingestUrl: (sourceUrl, conversationId) => request('/api/v1/ingest', {
    method: 'POST',
    body: JSON.stringify({ source_url: sourceUrl, conversation_id: conversationId }),
  }),

  ingestFile: (file, conversationId) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('conversation_id', conversationId);

    return request('/api/v1/ingest/file', {
      method: 'POST',
      body: formData,
    });
  },
};
