import React from 'react';
import { Cpu } from 'lucide-react';

export const Footer = () => {
  return (
    <footer className="footer">
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Cpu size={18} style={{ color: '#38bdf8' }} />
        <span style={{ color: 'var(--text-main)', fontWeight: 600 }}>Praxis AI Engine</span>
      </div>
      <div>Stateless Hierarchical Multi-Agent API Platform</div>
      <div>© {new Date().getFullYear()} Praxis AI. All rights reserved.</div>
    </footer>
  );
};
