import React from 'react';
import { Cpu } from 'lucide-react';

export const Footer = () => {
  return (
    <footer className="footer">
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <img src="/logo.png" alt="Praxis Logo" style={{ width: 20, height: 20, borderRadius: '4px', objectFit: 'contain' }} />
        <span style={{ color: 'var(--text-main)', fontWeight: 600 }}>Praxis.ai</span>
      </div>
      <div>© {new Date().getFullYear()} Praxis.ai. All rights reserved.</div>
    </footer>
  );
};
