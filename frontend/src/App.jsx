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
import { DocumentIngestModal } from './components/chat/DocumentIngestModal';
import { api } from './services/api';

import './styles/index.css';
import './styles/landing.css';
import './styles/auth.css';
import './styles/chat.css';

const MainLayout = () => {
  const { isAuthenticated, loading } = useAuth();
  const [currentView, setCurrentView] = useState(
    () => localStorage.getItem('praxis_view') || 'landing'
  ); // persist across refreshes
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authModalTab, setAuthModalTab] = useState('login');
  
  // Chat state
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);
  const [ingestModalOpen, setIngestModalOpen] = useState(false);
  const initialChatCreatedRef = useRef(false);

  // When authenticated & in chat view: load conversations (also fires on page refresh)
  useEffect(() => {
    if (isAuthenticated && currentView === 'chat') {
      loadConversations();
    }
    // If session expired / logged out while on chat, bounce back to landing
    if (!isAuthenticated && !loading && currentView === 'chat') {
      setCurrentView('landing');
      localStorage.setItem('praxis_view', 'landing');
    }
  }, [isAuthenticated, currentView, loading]);

  const loadConversations = async () => {
    try {
      const res = await api.getConversations();
      const list = res.conversations || [];
      setConversations(list);

      // On initial login / workspace launch: always start with a fresh new chat thread ONCE
      if (!initialChatCreatedRef.current) {
        initialChatCreatedRef.current = true;
        await handleCreateNewConversation();
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
    localStorage.setItem('praxis_view', 'chat');
  };

  const handleGoHome = () => {
    setCurrentView('landing');
    localStorage.setItem('praxis_view', 'landing');
  };

  const handleCreateNewConversation = async () => {
    try {
      const newConv = await api.createConversation('New Conversation');
      const convId = newConv.conversation_id;
      
      // Update state directly — NO recursive loadConversations() call!
      setActiveConvId(convId);
      setConversations((prev) => [
        {
          conversation_id: convId,
          title: 'New Conversation',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        ...prev,
      ]);
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
          onGoHome={handleGoHome}
        />
        <ChatWindow
          conversationId={activeConvId}
          activeTitle={conversations.find(c => c.conversation_id === activeConvId)?.title}
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
