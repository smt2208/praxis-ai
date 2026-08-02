import React from 'react';
import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';

export const ThemeToggle = () => {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <button
      onClick={toggleTheme}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '32px',
        height: '32px',
        borderRadius: '50%',
        background: 'var(--bg-card)',
        border: '1px solid var(--border-color)',
        color: 'var(--text-muted)',
        cursor: 'pointer',
        flexShrink: 0,
      }}
    >
      {isDark
        ? <Sun size={15} style={{ color: 'var(--accent-amber)' }} />
        : <Moon size={15} style={{ color: 'var(--primary)' }} />
      }
    </button>
  );
};
