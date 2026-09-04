import React, { useState, useEffect, useRef, useCallback } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { Navbar } from './components/common/Navbar';
import { HeroSection } from './components/landing/HeroSection';
import { ArchitectureShowcase } from './components/landing/ArchitectureShowcase';
import { FeatureGrid } from './components/landing/FeatureGrid';
import { Footer } from './components/landing/Footer';
import { AuthModal } from './components/auth/AuthModal';
import { VerifyEmailPage } from './components/auth/VerifyEmailPage';
import { ResetPasswordPage } from './components/auth/ResetPasswordPage';
import { Sidebar } from './components/chat/Sidebar';
import { ChatWindow } from './components/chat/ChatWindow';
import { ServerOfflineModal } from './components/common/ServerOfflineModal';
import { api } from './services/api';

import './styles/index.css';
import './styles/landing.css';
import './styles/auth.css';
import './styles/chat.css';

// Simple path-based routing — no router library needed
const currentPath = window.location.pathname;
const MainLayout = () => {
  const { isAuthenticated, loading } = useAuth();
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authModalTab, setAuthModalTab] = useState('login');

  // Chat state
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(() => typeof window !== 'undefined' && window.innerWidth > 768);
  const initialChatCreatedRef = useRef(false);

  // When user becomes authenticated, load their conversations
  useEffect(() => {
    if (isAuthenticated) {
      loadConversations();
    } else {
      // Session expired or logged out: reset chat state
      setConversations([]);
      setActiveConvId(null);
      setSidebarOpen(false);
      initialChatCreatedRef.current = false;
    }
  }, [isAuthenticated]);

  const loadConversations = async () => {
    try {
      const res = await api.getConversations();
      const list = res.conversations || [];
      setConversations(list);

      // On login / refresh: start with a fresh empty chat screen (ChatGPT/Claude flow)
      // Past conversations are listed in the sidebar for easy access
      if (!initialChatCreatedRef.current) {
        initialChatCreatedRef.current = true;
        setActiveConvId(null);
      }
    } catch (err) {
      console.error('Failed to load conversations:', err);
    }
  };

  const handleOpenAuth = (tab = 'login') => {
    setAuthModalTab(tab);
    setAuthModalOpen(true);
  };

  const handleCreateNewConversation = () => {
    // Simply reset to fresh chat screen without pre-creating an empty DB row
    setActiveConvId(null);
    setSidebarOpen(false);
  };

  const handleDeleteConversation = async (convId) => {
    try {
      await api.deleteConversation(convId);
      // Remove from local list
      setConversations((prev) => prev.filter(c => c.conversation_id !== convId));
      // If the deleted one was active, open a new conversation
      if (convId === activeConvId) {
        await handleCreateNewConversation();
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
  };

  if (loading) {
    return (
      <div className="app-loading">
        <img src="/logo.png" alt="Praxis" style={{ width: 44, height: 44, borderRadius: 12 }} />
        <div className="app-loading-ring" />
        <p className="app-loading-text">Loading Praxis...</p>
      </div>
    );
  }

  // ─── If authenticated → always go straight to the chat workspace ───
  if (isAuthenticated) {
    const handleSelectConv = (id) => {
      setActiveConvId(id);
      if (window.innerWidth <= 768) {
        setSidebarOpen(false);
      }
    };

    return (
      <div className="chat-workspace">
        <Sidebar
          conversations={conversations}
          activeConvId={activeConvId}
          onSelectConv={handleSelectConv}
          onNewConv={handleCreateNewConversation}
          onDeleteConv={handleDeleteConversation}
          isOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen(prev => !prev)}
          onClose={() => setSidebarOpen(false)}
        />
        <ChatWindow
          conversationId={activeConvId}
          activeTitle={conversations.find(c => c.conversation_id === activeConvId)?.title}
          onRefreshConversations={loadConversations}
          onSelectActiveConv={(convId) => setActiveConvId(convId)}
          onToggleSidebar={() => setSidebarOpen(prev => !prev)}
          sidebarOpen={sidebarOpen}
        />
      </div>
    );
  }

  // ─── Not authenticated → show the landing page ───
  return (
    <div className="landing-page">
      <Navbar
        onOpenAuth={handleOpenAuth}
        onGoToChat={() => handleOpenAuth('register')}
      />

      <main>
        <HeroSection
          onOpenAuth={handleOpenAuth}
          onGoToChat={() => handleOpenAuth('register')}
        />
        <ArchitectureShowcase />
        <FeatureGrid />
      </main>

      <Footer />

      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        initialTab={authModalTab}
      />
    </div>
  );
};

export default function App() {
  const [serverOffline, setServerOffline] = useState(false);
  const [serverChecked, setServerChecked] = useState(false);

  const checkServerHealth = useCallback(async () => {
    try {
      const API_BASE = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');
      const res = await fetch(`${API_BASE}/health`, {
        signal: AbortSignal.timeout(4000),
      });
      setServerOffline(!res.ok);
    } catch {
      setServerOffline(true);
    } finally {
      setServerChecked(true);
    }
  }, []);

  useEffect(() => {
    checkServerHealth();
  }, [checkServerHealth]);

  // Don't render anything until we know the server status
  if (!serverChecked) return null;

  // Show offline modal on top of (or instead of) the app
  if (serverOffline) {
    return (
      <ThemeProvider>
        <ServerOfflineModal onRetry={checkServerHealth} />
      </ThemeProvider>
    );
  }

  // Render the password reset page for users arriving from the reset email link
  if (currentPath === '/reset-password') {
    return (
      <ThemeProvider>
        <ResetPasswordPage
          onGoToLogin={() => {
            window.history.pushState({}, '', '/');
            window.location.reload();
          }}
        />
      </ThemeProvider>
    );
  }

  // Render the email verification page for users arriving from the email link
  if (currentPath === '/verify-email') {
    return (
      <ThemeProvider>
        <VerifyEmailPage
          onGoToLogin={() => {
            window.history.pushState({}, '', '/');
            window.location.reload();
          }}
        />
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider>
      <AuthProvider>
        <MainLayout />
      </AuthProvider>
    </ThemeProvider>
  );
}
