import React from 'react';
import { Cpu, LogIn, UserPlus, LogOut, MessageSquare } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export const Navbar = ({ onOpenAuth, onGoToChat }) => {
  const { isAuthenticated, user, logout } = useAuth();

  return (
    <header className="navbar">
      <a href="#" className="nav-brand">
        <div className="brand-icon">
          <Cpu size={22} />
        </div>
        <span>Praxis AI</span>
      </a>

      <div className="nav-actions">
        {isAuthenticated ? (
          <>
            <button className="btn btn-primary" onClick={onGoToChat}>
              <MessageSquare size={18} />
              <span>Launch Workspace</span>
            </button>
            <button className="btn btn-secondary" onClick={() => logout(false)}>
              <LogOut size={18} />
              <span>Logout</span>
            </button>
          </>
        ) : (
          <>
            <button className="btn btn-secondary" onClick={() => onOpenAuth('login')}>
              <LogIn size={18} />
              <span>Sign In</span>
            </button>
            <button className="btn btn-primary" onClick={() => onOpenAuth('register')}>
              <UserPlus size={18} />
              <span>Get Started</span>
            </button>
          </>
        )}
      </div>
    </header>
  );
};
