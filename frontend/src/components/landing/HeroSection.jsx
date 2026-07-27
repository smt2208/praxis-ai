import React from 'react';
import { ArrowRight, Sparkles, ShieldCheck, Zap, BookOpenCheck } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export const HeroSection = ({ onOpenAuth, onGoToChat }) => {
  const { isAuthenticated } = useAuth();

  return (
    <section className="hero-section">
      <div className="hero-pill">
        <Sparkles size={16} />
        <span>Next-Generation AI Intelligence</span>
      </div>

      <h1 className="hero-title">
        Supercharge Your Thinking with <span className="gradient-text">Praxis</span>
      </h1>

      <p className="hero-description">
        An intelligent AI workspace built to help you write, research, analyze complex 
        documents, and get accurate answers, powered by a team of specialized AI experts.
      </p>

      <div className="hero-ctas">
        {isAuthenticated ? (
          <button className="btn btn-primary" style={{ padding: '14px 28px', fontSize: '1.05rem' }} onClick={onGoToChat}>
            <span>Start Chatting Now</span>
            <ArrowRight size={20} />
          </button>
        ) : (
          <>
            <button
              className="btn btn-primary"
              style={{ padding: '14px 28px', fontSize: '1.05rem' }}
              onClick={() => onOpenAuth('register')}
            >
              <span>Try Praxis Free</span>
              <ArrowRight size={20} />
            </button>
            <button
              className="btn btn-secondary"
              style={{ padding: '14px 28px', fontSize: '1.05rem' }}
              onClick={() => onOpenAuth('login')}
            >
              <span>Sign In</span>
            </button>
          </>
        )}
      </div>

      <div style={{ marginTop: '48px', display: 'flex', gap: '32px', color: 'var(--text-dim)', fontSize: '0.9rem', flexWrap: 'wrap', justifyContent: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Zap size={18} style={{ color: '#38bdf8' }} />
          <span>Lightning Fast & Factual</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ShieldCheck size={18} style={{ color: '#34d399' }} />
          <span>Private & Secure Workspace</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <BookOpenCheck size={18} style={{ color: '#818cf8' }} />
          <span>Chat with Any Document</span>
        </div>
      </div>
    </section>
  );
};
