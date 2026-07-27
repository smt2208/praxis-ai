import React, { useState, useEffect, useRef } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/common/Navbar';
import { HeroSection } from './components/landing/HeroSection';
import { ArchitectureShowcase } from './components/landing/ArchitectureShowcase';
import { FeatureGrid } from './components/landing/FeatureGrid';
import { Footer } from './components/landing/Footer';
import { AuthModal } from './components/auth/AuthModal';
import { Sidebar } from './components/chat/Sidebar';
import { ChatWindow } from './components/chat/ChatWindow';
import { api } from './services/api';

import './styles/index.css';
import './styles/landing.css';
import './styles/auth.css';
import './styles/chat.css';

const MainLayout = () => {
  const { isAuthenticated, loading } = useAuth();
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authModalTab, setAuthModalTab] = useState('login');

  // Chat state
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
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
      <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', background: '#090d16', color: '#38bdf8' }}>
        <div>Loading Praxis...</div>
      </div>
    );
  }

  // ─── If authenticated → always go straight to the chat workspace ───
  if (isAuthenticated) {
    return (
      <div className="chat-workspace">
        <Sidebar
          conversations={conversations}
          activeConvId={activeConvId}
          onSelectConv={(id) => { setActiveConvId(id); setSidebarOpen(false); }}
          onNewConv={handleCreateNewConversation}
          onDeleteConv={handleDeleteConversation}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />
        <ChatWindow
          conversationId={activeConvId}
          activeTitle={conversations.find(c => c.conversation_id === activeConvId)?.title}
          onRefreshConversations={loadConversations}
          onSelectActiveConv={(convId) => setActiveConvId(convId)}
          onToggleSidebar={() => setSidebarOpen(prev => !prev)}
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
  return (
    <AuthProvider>
      <MainLayout />
    </AuthProvider>
  );
}
