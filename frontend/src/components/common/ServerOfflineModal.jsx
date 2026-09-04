import React, { useState } from 'react';

// ─── Update these two constants with your own values ─────────────────────────
const GITHUB_URL = 'https://github.com/smt2208/praxis-ai';
const CONTACT_EMAIL = 'tripathishyam22@gmail.com';
// ─────────────────────────────────────────────────────────────────────────────

const REQUEST_HREF = `mailto:${CONTACT_EMAIL}?subject=Praxis%20Demo%20Request&body=Hi%2C%20I%27d%20love%20to%20check%20out%20a%20live%20demo%20of%20Praxis!%20Could%20you%20please%20turn%20on%20the%20server%3F`;

export function ServerOfflineModal({ onRetry }) {
  const [retrying, setRetrying] = useState(false);

  const handleRetry = async () => {
    setRetrying(true);
    await onRetry();
    setTimeout(() => setRetrying(false), 2500);
  };

  return (
    <>
      {/* Keyframe animations — injected inline so no extra CSS file is needed */}
      <style>{`
        @keyframes offlineModalIn {
          from { opacity: 0; transform: scale(0.92) translateY(14px); }
          to   { opacity: 1; transform: scale(1)   translateY(0);    }
        }
        @keyframes pulseDot {
          0%, 100% { opacity: 1; box-shadow: 0 0 0 0   rgba(248,113,113,0.7); }
          50%       { opacity: 0.7; box-shadow: 0 0 0 6px rgba(248,113,113,0);   }
        }
        @keyframes spinIcon { to { transform: rotate(360deg); } }
        .om-ghost:hover  { background: rgba(255,255,255,0.06) !important; border-color: rgba(255,255,255,0.22) !important; }
        .om-retry:hover  { color: #8b5cf6 !important; }
      `}</style>

      <div style={S.overlay}>
        <div style={S.modal}>

          {/* Status badge */}
          <div style={S.statusRow}>
            <span style={S.dot} />
            <span style={S.statusLabel}>Server Offline</span>
          </div>

          {/* Server icon */}
          <div style={S.iconWrap}>
            <svg width="44" height="44" viewBox="0 0 24 24" fill="none"
              stroke="#8b5cf6" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="2" width="20" height="8" rx="2" />
              <rect x="2" y="14" width="20" height="8" rx="2" />
              <line x1="6" y1="6"  x2="6.01" y2="6"  />
              <line x1="6" y1="18" x2="6.01" y2="18" />
            </svg>
          </div>

          {/* Heading */}
          <h2 style={S.heading}>Praxis is currently offline</h2>

          {/* Message */}
          <p style={S.body}>
            Hey! 👋 Praxis runs on an <strong style={{ color: '#e6edf3' }}>AWS EC2</strong> instance.
            As a student developer, I keep it stopped when not actively demoing to avoid AWS costs — bills are real! 😅
          </p>
          <p style={S.body}>
            Feel free to explore the full codebase on GitHub, or reach out and I'll spin up
            the server for a live walkthrough — usually up within a few minutes.
          </p>

          {/* Buttons */}
          <div style={S.btnRow}>
            <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer"
              className="om-ghost" style={S.btnGhost}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"
                style={{ marginRight: 6, flexShrink: 0 }}>
                <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" />
              </svg>
              View on GitHub
            </a>

            <a href={REQUEST_HREF} style={S.btnPrimary}>
              ✉️&nbsp; Request Live Demo
            </a>
          </div>

          {/* Retry */}
          <button onClick={handleRetry} disabled={retrying}
            className="om-retry" style={S.retryBtn}>
            {retrying
              ? <><span style={S.spinner} /> Checking server…</>
              : '↻  Try connecting again'}
          </button>

        </div>
      </div>
    </>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const S = {
  overlay: {
    position: 'fixed',
    inset: 0,
    zIndex: 9999,
    background: 'rgba(0,0,0,0.78)',
    backdropFilter: 'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '1rem',
  },
  modal: {
    background: '#161b22',
    border: '1px solid rgba(139,92,246,0.22)',
    borderRadius: '18px',
    padding: '2.75rem 2.25rem 2rem',
    maxWidth: '480px',
    width: '100%',
    textAlign: 'center',
    boxShadow: '0 0 80px rgba(139,92,246,0.1), 0 32px 80px rgba(0,0,0,0.65)',
    animation: 'offlineModalIn 0.4s cubic-bezier(0.34,1.56,0.64,1) both',
    fontFamily: "'Plus Jakarta Sans', sans-serif",
  },
  statusRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    marginBottom: '1.4rem',
  },
  dot: {
    display: 'inline-block',
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: '#f87171',
    animation: 'pulseDot 1.8s ease-in-out infinite',
  },
  statusLabel: {
    fontSize: '0.75rem',
    fontWeight: 700,
    color: '#f87171',
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
  },
  iconWrap: {
    display: 'flex',
    justifyContent: 'center',
    marginBottom: '1.25rem',
  },
  heading: {
    fontSize: '1.38rem',
    fontWeight: 700,
    color: '#e6edf3',
    margin: '0 0 1rem',
    lineHeight: 1.3,
  },
  body: {
    fontSize: '0.9rem',
    color: '#8b949e',
    lineHeight: 1.7,
    margin: '0 0 0.65rem',
  },
  btnRow: {
    display: 'flex',
    gap: '12px',
    justifyContent: 'center',
    marginTop: '1.85rem',
    flexWrap: 'wrap',
  },
  btnGhost: {
    display: 'inline-flex',
    alignItems: 'center',
    padding: '0.58rem 1.15rem',
    borderRadius: '9px',
    border: '1px solid rgba(255,255,255,0.12)',
    color: '#e6edf3',
    background: 'transparent',
    fontSize: '0.875rem',
    fontWeight: 500,
    textDecoration: 'none',
    cursor: 'pointer',
    transition: 'background 0.18s, border-color 0.18s',
  },
  btnPrimary: {
    display: 'inline-flex',
    alignItems: 'center',
    padding: '0.58rem 1.3rem',
    borderRadius: '9px',
    border: 'none',
    color: '#fff',
    background: 'linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%)',
    fontSize: '0.875rem',
    fontWeight: 600,
    textDecoration: 'none',
    cursor: 'pointer',
    boxShadow: '0 4px 22px rgba(139,92,246,0.38)',
  },
  retryBtn: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    marginTop: '1.3rem',
    background: 'none',
    border: 'none',
    color: '#484f58',
    fontSize: '0.82rem',
    cursor: 'pointer',
    transition: 'color 0.18s',
    fontFamily: "'Plus Jakarta Sans', sans-serif",
  },
  spinner: {
    display: 'inline-block',
    width: 11,
    height: 11,
    border: '2px solid #484f58',
    borderTopColor: '#8b5cf6',
    borderRadius: '50%',
    animation: 'spinIcon 0.65s linear infinite',
  },
};

