import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { X, User, Brain, Trash2, Check, Shield, AlertTriangle, Briefcase, MapPin, Calendar } from 'lucide-react';

export const SettingsModal = ({ isOpen, onClose }) => {
  const { user, updateProfile, toggleMemory, clearMemory } = useAuth();
  const [activeTab, setActiveTab] = useState('general');

  // Extended Profile Form state
  const [profileForm, setProfileForm] = useState({
    fullName: '',
    age: '',
    profession: '',
    city: '',
    state: '',
    country: '',
  });
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState(false);

  // Memory states
  const [memoryEnabled, setMemoryEnabled] = useState(true);
  const [togglingMem, setTogglingMem] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [clearingMem, setClearingMem] = useState(false);

  useEffect(() => {
    if (user) {
      setProfileForm({
        fullName: user.full_name || '',
        age: user.age ? String(user.age) : '',
        profession: user.profession || '',
        city: user.city || '',
        state: user.state || '',
        country: user.country || '',
      });
      setMemoryEnabled(user.memory_enabled !== false);
    }
  }, [user, isOpen]);

  if (!isOpen) return null;

  const handleChange = (e) => {
    const { name, value } = e.target;
    setProfileForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    setSavingProfile(true);
    const parsedAge = profileForm.age ? parseInt(profileForm.age, 10) : null;
    const payload = {
      full_name: profileForm.fullName.trim(),
      age: isNaN(parsedAge) ? null : parsedAge,
      profession: profileForm.profession.trim(),
      city: profileForm.city.trim(),
      state: profileForm.state.trim(),
      country: profileForm.country.trim(),
    };

    const res = await updateProfile(payload);
    setSavingProfile(false);
    if (res.success) {
      setProfileSuccess(true);
      setTimeout(() => setProfileSuccess(false), 2500);
    }
  };

  const handleToggleMemory = async () => {
    const nextState = !memoryEnabled;
    setMemoryEnabled(nextState);
    setTogglingMem(true);
    const res = await toggleMemory(nextState);
    setTogglingMem(false);
    if (!res.success) {
      setMemoryEnabled(!nextState);
    }
  };

  const handleClearMemory = async () => {
    setClearingMem(true);
    await clearMemory();
    setClearingMem(false);
    setConfirmClear(false);
  };

  return (
    <div className="auth-modal-overlay" onClick={onClose}>
      <div
        className="auth-modal-container settings-modal-container"
        style={{ maxWidth: '650px', width: '94%', padding: '0', overflow: 'hidden' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '20px 24px',
            borderBottom: '1px solid var(--border-color)',
            background: 'rgba(15, 23, 42, 0.95)',
          }}
        >
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '10px' }}>
            Settings
          </h2>
          <button className="modal-close-btn" style={{ top: '16px', right: '16px' }} onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Modal Body with Left Navigation Sidebar */}
        <div className="settings-modal-body" style={{ display: 'flex', minHeight: '380px' }}>
          {/* Tab Sidebar */}
          <div
            className="settings-modal-tabs"
            style={{
              width: '180px',
              borderRight: '1px solid var(--border-color)',
              background: 'rgba(15, 23, 42, 0.5)',
              padding: '12px',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
            }}
          >
            <button
              onClick={() => setActiveTab('general')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '10px 14px',
                borderRadius: 'var(--radius-md)',
                background: activeTab === 'general' ? 'rgba(129, 140, 248, 0.15)' : 'transparent',
                color: activeTab === 'general' ? 'var(--primary)' : 'var(--text-muted)',
                fontWeight: activeTab === 'general' ? 600 : 400,
                border: 'none',
                cursor: 'pointer',
                textAlign: 'left',
                fontSize: '0.9rem',
                transition: 'all 0.15s ease',
              }}
            >
              <User size={16} /> General Profile
            </button>

            <button
              onClick={() => setActiveTab('personalisation')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '10px 14px',
                borderRadius: 'var(--radius-md)',
                background: activeTab === 'personalisation' ? 'rgba(129, 140, 248, 0.15)' : 'transparent',
                color: activeTab === 'personalisation' ? 'var(--primary)' : 'var(--text-muted)',
                fontWeight: activeTab === 'personalisation' ? 600 : 400,
                border: 'none',
                cursor: 'pointer',
                textAlign: 'left',
                fontSize: '0.9rem',
                transition: 'all 0.15s ease',
              }}
            >
              <Brain size={16} /> Personalisation
            </button>
          </div>

          {/* Tab Content */}
          <div style={{ flex: 1, padding: '24px', overflowY: 'auto', maxHeight: '480px' }}>
            {activeTab === 'general' && (
              <div>
                <div style={{ marginBottom: '16px' }}>
                  <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: '4px' }}>
                    Personal Information
                  </h3>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    Add your profile details to help Praxis tailor responses and context specifically to you.
                  </p>
                </div>

                <form onSubmit={handleSaveProfile} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {/* Name & Age Row */}
                  <div className="settings-form-row" style={{ display: 'flex', gap: '12px' }}>
                    <div className="input-group" style={{ flex: 2 }}>
                      <label className="input-label" htmlFor="settings-name">
                        What should I call you?
                      </label>
                      <input
                        id="settings-name"
                        type="text"
                        name="fullName"
                        value={profileForm.fullName}
                        onChange={handleChange}
                        placeholder="e.g. Alex Johnson"
                        className="input-field"
                      />
                    </div>

                    <div className="input-group" style={{ flex: 1 }}>
                      <label className="input-label" htmlFor="settings-age">
                        Age
                      </label>
                      <input
                        id="settings-age"
                        type="number"
                        name="age"
                        min="1"
                        max="120"
                        value={profileForm.age}
                        onChange={handleChange}
                        placeholder="e.g. 28"
                        className="input-field"
                      />
                    </div>
                  </div>

                  {/* Profession */}
                  <div className="input-group">
                    <label className="input-label" htmlFor="settings-profession">
                      Profession / Work
                    </label>
                    <input
                      id="settings-profession"
                      type="text"
                      name="profession"
                      value={profileForm.profession}
                      onChange={handleChange}
                      placeholder="e.g. Software Engineer, Researcher, Student"
                      className="input-field"
                    />
                  </div>

                  {/* Location Row: City, State, Country */}
                  <div className="settings-form-row" style={{ display: 'flex', gap: '10px' }}>
                    <div className="input-group" style={{ flex: 1 }}>
                      <label className="input-label" htmlFor="settings-city">
                        City
                      </label>
                      <input
                        id="settings-city"
                        type="text"
                        name="city"
                        value={profileForm.city}
                        onChange={handleChange}
                        placeholder="e.g. San Francisco"
                        className="input-field"
                      />
                    </div>

                    <div className="input-group" style={{ flex: 1 }}>
                      <label className="input-label" htmlFor="settings-state">
                        State
                      </label>
                      <input
                        id="settings-state"
                        type="text"
                        name="state"
                        value={profileForm.state}
                        onChange={handleChange}
                        placeholder="e.g. California"
                        className="input-field"
                      />
                    </div>

                    <div className="input-group" style={{ flex: 1 }}>
                      <label className="input-label" htmlFor="settings-country">
                        Country
                      </label>
                      <input
                        id="settings-country"
                        type="text"
                        name="country"
                        value={profileForm.country}
                        onChange={handleChange}
                        placeholder="e.g. USA"
                        className="input-field"
                      />
                    </div>
                  </div>

                  {/* Email Field (Disabled) */}
                  <div className="input-group">
                    <label className="input-label" htmlFor="settings-email">
                      Email Address
                    </label>
                    <div style={{ position: 'relative' }}>
                      <input
                        id="settings-email"
                        type="email"
                        value={user?.email || ''}
                        disabled
                        className="input-field"
                        style={{ opacity: 0.65, cursor: 'not-allowed', paddingRight: '36px' }}
                      />
                      <Shield size={16} style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
                    </div>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '10px' }}>
                    <button
                      type="submit"
                      disabled={savingProfile}
                      style={{
                        padding: '9px 22px',
                        borderRadius: 'var(--radius-md)',
                        background: profileSuccess ? 'var(--accent-emerald)' : 'var(--primary)',
                        color: '#04111d',
                        fontWeight: 600,
                        border: 'none',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        fontSize: '0.9rem',
                        transition: 'all 0.2s ease',
                      }}
                    >
                      {profileSuccess ? <><Check size={16} /> Saved</> : savingProfile ? 'Saving...' : 'Save Profile'}
                    </button>
                  </div>
                </form>
              </div>
            )}

            {activeTab === 'personalisation' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                <div>
                  <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '4px', color: 'var(--text-main)' }}>
                    Long-Term Memory
                  </h3>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                    Praxis remembers facts about your preferences and projects across chat sessions to give tailored responses.
                  </p>
                </div>

                {/* Memory Toggle Row */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '16px',
                    borderRadius: 'var(--radius-md)',
                    background: 'rgba(30, 41, 59, 0.5)',
                    border: '1px solid var(--border-color)',
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.92rem' }}>Memory</span>
                    <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                      {memoryEnabled ? 'Praxis will remember facts from your messages.' : 'Memory is disabled. Past memories will not be accessed.'}
                    </span>
                  </div>

                  {/* Custom Switch Component */}
                  <button
                    type="button"
                    role="switch"
                    aria-checked={memoryEnabled}
                    disabled={togglingMem}
                    onClick={handleToggleMemory}
                    style={{
                      width: '48px',
                      height: '26px',
                      borderRadius: '999px',
                      background: memoryEnabled ? 'var(--primary)' : 'rgba(255, 255, 255, 0.15)',
                      border: 'none',
                      position: 'relative',
                      cursor: 'pointer',
                      transition: 'background 0.25s ease',
                      padding: '3px',
                      flexShrink: 0,
                    }}
                  >
                    <div
                      style={{
                        width: '20px',
                        height: '20px',
                        borderRadius: '50%',
                        background: memoryEnabled ? '#04111d' : '#94a3b8',
                        transform: memoryEnabled ? 'translateX(22px)' : 'translateX(0)',
                        transition: 'transform 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
                      }}
                    />
                  </button>
                </div>

                {/* Clear Memory Section */}
                <div
                  style={{
                    padding: '16px',
                    borderRadius: 'var(--radius-md)',
                    background: 'rgba(244, 63, 94, 0.05)',
                    border: '1px solid rgba(244, 63, 94, 0.2)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.92rem', color: '#f87171' }}>Clear Memory</span>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      Permanently wipe all long-term memories Praxis has stored about you.
                    </span>
                  </div>

                  {!confirmClear ? (
                    <button
                      type="button"
                      onClick={() => setConfirmClear(true)}
                      style={{
                        alignSelf: 'flex-start',
                        padding: '8px 14px',
                        borderRadius: 'var(--radius-sm)',
                        background: 'rgba(244, 63, 94, 0.15)',
                        border: '1px solid rgba(244, 63, 94, 0.3)',
                        color: '#fca5a5',
                        fontWeight: 600,
                        fontSize: '0.85rem',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        transition: 'all 0.2s ease',
                      }}
                    >
                      <Trash2 size={15} /> Clear All Memories
                    </button>
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{ fontSize: '0.8rem', color: '#fca5a5', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <AlertTriangle size={14} /> Are you sure?
                      </span>
                      <button
                        type="button"
                        disabled={clearingMem}
                        onClick={handleClearMemory}
                        style={{
                          padding: '6px 12px',
                          borderRadius: 'var(--radius-sm)',
                          background: 'var(--accent-rose)',
                          color: '#04111d',
                          fontWeight: 700,
                          fontSize: '0.82rem',
                          border: 'none',
                          cursor: 'pointer',
                        }}
                      >
                        {clearingMem ? 'Clearing...' : 'Yes, Delete All'}
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmClear(false)}
                        style={{
                          padding: '6px 12px',
                          borderRadius: 'var(--radius-sm)',
                          background: 'rgba(255, 255, 255, 0.1)',
                          color: 'var(--text-muted)',
                          fontSize: '0.82rem',
                          border: 'none',
                          cursor: 'pointer',
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
