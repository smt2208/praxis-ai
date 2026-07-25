import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/common/Navbar';
import { HeroSection } from './components/landing/HeroSection';
import { ArchitectureShowcase } from './components/landing/ArchitectureShowcase';
import { FeatureGrid } from './components/landing/FeatureGrid';
import { Footer } from './components/landing/Footer';
import { AuthModal } from './components/auth/AuthModal';
import { Sidebar } from './components/chat/Sidebar';
import { ChatWindow } from './components/chat/ChatWindow';
import { DocumentIngestModal } from './components/chat/DocumentIngestModal';
import { api } from './services/api';

import './styles/index.css';
import './styles/landing.css';
import './styles/auth.css';
import './styles/chat.css';

const MainLayout = () => {
  const { isAuthenticated, loading } = useAuth();
  const [currentView, setCurrentView] = useState('landing'); // 'landing' or 'chat'
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authModalTab, setAuthModalTab] = useState('login');
  
  // Chat state
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);
  const [ingestModalOpen, setIngestModalOpen] = useState(false);

  // Switch to chat view if authenticated and user clicks launch
  useEffect(() => {
    if (isAuthenticated && currentView === 'chat') {
      loadConversations();
    }
  }, [isAuthenticated, currentView]);

  const loadConversations = async () => {
    try {
      const res = await api.getConversations();
      const list = res.conversations || [];
      setConversations(list);

      // Select first conversation or auto-create if empty
      if (list.length > 0 && !activeConvId) {
        setActiveConvId(list[0].conversation_id);
      } else if (list.length === 0) {
        handleCreateNewConversation();
      }
    } catch (err) {
      console.error('Failed to load conversations:', err);
    }
  };

  const handleOpenAuth = (tab = 'login') => {
    setAuthModalTab(tab);
    setAuthModalOpen(true);
  };

  const handleGoToChat = () => {
    if (!isAuthenticated) {
      handleOpenAuth('login');
      return;
    }
    setCurrentView('chat');
  };

  const handleCreateNewConversation = async () => {
    try {
      const newConv = await api.createConversation(`Session #${conversations.length + 1}`);
      const convId = newConv.conversation_id;
      setActiveConvId(convId);
      loadConversations();
    } catch (err) {
      console.error('Failed to create new conversation:', err);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', background: '#090d16', color: '#38bdf8' }}>
        <div>Loading Praxis AI...</div>
      </div>
    );
  }

  // Render Chat Workspace
  if (currentView === 'chat' && isAuthenticated) {
    return (
      <div className="chat-workspace">
        <Sidebar
          conversations={conversations}
          activeConvId={activeConvId}
          onSelectConv={(id) => setActiveConvId(id)}
          onNewConv={handleCreateNewConversation}
          onOpenIngest={() => setIngestModalOpen(true)}
          onGoHome={() => setCurrentView('landing')}
        />
        <ChatWindow
          conversationId={activeConvId}
          activeTitle={conversations.find(c => c.conversation_id === activeConvId)?.title}
          onOpenIngest={() => setIngestModalOpen(true)}
          onRefreshConversations={loadConversations}
        />
        <DocumentIngestModal
          isOpen={ingestModalOpen}
          onClose={() => setIngestModalOpen(false)}
          conversationId={activeConvId}
        />
      </div>
    );
  }

  // Render Landing Page View
  return (
    <div className="landing-page">
      <Navbar
        onOpenAuth={handleOpenAuth}
        onGoToChat={handleGoToChat}
      />
      
      <main>
        <HeroSection
          onOpenAuth={handleOpenAuth}
          onGoToChat={handleGoToChat}
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
