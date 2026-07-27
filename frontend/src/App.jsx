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
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authModalTab, setAuthModalTab] = useState('login');

  // Chat state
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);
  const [ingestModalOpen, setIngestModalOpen] = useState(false);
  const initialChatCreatedRef = useRef(false);

  // When user becomes authenticated, load their conversations
  useEffect(() => {
    if (isAuthenticated) {
      loadConversations();
    } else {
      // Session expired or logged out: reset chat state
      setConversations([]);
      setActiveConvId(null);
      initialChatCreatedRef.current = false;
    }
  }, [isAuthenticated]);

  const loadConversations = async () => {
    try {
      const res = await api.getConversations();
      const list = res.conversations || [];
      setConversations(list);

      // Start with a fresh new chat thread once per session
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

  const handleCreateNewConversation = async () => {
    try {
      const newConv = await api.createConversation('New Conversation');
      const convId = newConv.conversation_id;

      // Update state directly — no recursive loadConversations() call
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

  // ─── If authenticated → always go straight to the chat workspace ───
  if (isAuthenticated) {
    return (
      <div className="chat-workspace">
        <Sidebar
          conversations={conversations}
          activeConvId={activeConvId}
          onSelectConv={(id) => setActiveConvId(id)}
          onNewConv={handleCreateNewConversation}
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

  // ─── Not authenticated → show the landing page ───
  return (
    <div className="landing-page">
      <Navbar
        onOpenAuth={handleOpenAuth}
        onGoToChat={() => handleOpenAuth('login')}
      />

      <main>
        <HeroSection
          onOpenAuth={handleOpenAuth}
          onGoToChat={() => handleOpenAuth('login')}
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
