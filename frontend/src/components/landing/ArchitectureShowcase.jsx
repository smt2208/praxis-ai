import React from 'react';
import { Sparkles, BookOpen, Compass } from 'lucide-react';

export const ArchitectureShowcase = () => {
  return (
    <section className="architecture-section">
      <div className="section-header">
        <span className="badge badge-primary" style={{ marginBottom: '12px' }}>Smart Intelligence</span>
        <h2>Tailored AI Experts for Every Task</h2>
        <p>Praxis AI routes your questions to specialized engines designed for maximum accuracy</p>
      </div>

      <div className="swarm-grid">
        <div className="glass-panel swarm-card">
          <div className="swarm-card-icon" style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8' }}>
            <Sparkles size={24} />
          </div>
          <h3>Smart Conversation</h3>
          <p>
            Handles everyday questions, creative writing, brainstorms, and casual chat with instant, 
            natural context awareness.
          </p>
        </div>

        <div className="glass-panel swarm-card">
          <div className="swarm-card-icon" style={{ background: 'rgba(129, 140, 248, 0.15)', color: '#818cf8' }}>
            <BookOpen size={24} />
          </div>
          <h3>Document Intelligence</h3>
          <p>
            Upload your files, PDFs, or research notes and get instant, accurate answers 
            cross-referenced with up-to-date web information.
          </p>
        </div>

        <div className="glass-panel swarm-card">
          <div className="swarm-card-icon" style={{ background: 'rgba(52, 211, 153, 0.15)', color: '#34d399' }}>
            <Compass size={24} />
          </div>
          <h3>Deep Research Agent</h3>
          <p>
            Automatically breaks down complex topics into multi-step investigations, searching web and 
            academic sources to write complete research reports.
          </p>
        </div>
      </div>
    </section>
  );
};
