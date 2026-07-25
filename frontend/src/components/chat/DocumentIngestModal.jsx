import React, { useState } from 'react';
import { X, FileUp, Link, Upload, CheckCircle2, AlertCircle } from 'lucide-react';
import { api } from '../../services/api';

export const DocumentIngestModal = ({ isOpen, onClose, conversationId }) => {
  const [activeTab, setActiveTab] = useState('file'); // 'file' or 'url'
  const [urlInput, setUrlInput] = useState('');
  const [fileInput, setFileInput] = useState(null);
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);

  if (!isOpen) return null;

  const handleIngestUrl = async (e) => {
    e.preventDefault();
    if (!urlInput.trim()) return;

    setLoading(true);
    setStatusMsg(null);

    try {
      const res = await api.ingestUrl(urlInput.trim(), conversationId);
      setStatusMsg({ type: 'success', text: `Success! ${res.documents_stored} document chunks ingested.` });
      setUrlInput('');
      setTimeout(() => onClose(), 1500);
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message || 'Ingestion failed' });
    } finally {
      setLoading(false);
    }
  };

  const handleIngestFile = async (e) => {
    e.preventDefault();
    if (!fileInput) return;

    setLoading(true);
    setStatusMsg(null);

    try {
      const res = await api.ingestFile(fileInput, conversationId);
      setStatusMsg({ type: 'success', text: `Success! ${res.documents_stored} document chunks stored.` });
      setFileInput(null);
      setTimeout(() => onClose(), 1500);
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message || 'File ingestion failed' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-modal-overlay" onClick={onClose}>
      <div className="auth-modal-container" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '500px' }}>
        <button className="modal-close-btn" onClick={onClose}>
          <X size={20} />
        </button>

        <div className="auth-header" style={{ marginBottom: '16px' }}>
          <div style={{ display: 'inline-flex', color: '#34d399', marginBottom: '8px' }}>
            <FileUp size={28} />
          </div>
          <h3>Ingest Knowledge Document</h3>
          <p>Add documents to train the Knowledge Team for this chat</p>
        </div>

        <div className="auth-tabs">
          <button
            className={`auth-tab ${activeTab === 'file' ? 'active' : ''}`}
            onClick={() => { setActiveTab('file'); setStatusMsg(null); }}
          >
            File Upload
          </button>
          <button
            className={`auth-tab ${activeTab === 'url' ? 'active' : ''}`}
            onClick={() => { setActiveTab('url'); setStatusMsg(null); }}
          >
            Public URL / S3
          </button>
        </div>

        {statusMsg && (
          <div
            className="auth-alert"
            style={{
              background: statusMsg.type === 'success' ? 'rgba(52, 211, 153, 0.12)' : 'rgba(244, 63, 94, 0.12)',
              borderColor: statusMsg.type === 'success' ? 'rgba(52, 211, 153, 0.3)' : 'rgba(244, 63, 94, 0.3)',
              color: statusMsg.type === 'success' ? '#6ee7b7' : '#fca5a5',
            }}
          >
            {statusMsg.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
            <span>{statusMsg.text}</span>
          </div>
        )}

        {activeTab === 'file' ? (
          <form onSubmit={handleIngestFile}>
            <div className="input-group">
              <label className="input-label">Select Document (PDF, DOCX, TXT)</label>
              <input
                type="file"
                className="input-field"
                onChange={(e) => setFileInput(e.target.files[0] || null)}
                accept=".pdf,.docx,.pptx,.txt,.md"
                disabled={loading}
              />
              {fileInput && (
                <span style={{ fontSize: '0.8rem', color: 'var(--primary)', marginTop: '4px' }}>
                  Selected: {fileInput.name} ({Math.round(fileInput.size / 1024)} KB)
                </span>
              )}
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', marginTop: '12px' }}
              disabled={loading || !fileInput}
            >
              {loading ? 'Ingesting with LlamaParse...' : 'Upload & Parse Document'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleIngestUrl}>
            <div className="input-group">
              <label className="input-label">Document Public URL</label>
              <input
                type="url"
                className="input-field"
                placeholder="https://example.com/paper.pdf"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                disabled={loading}
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', marginTop: '12px' }}
              disabled={loading || !urlInput.trim()}
            >
              {loading ? 'Downloading & Parsing...' : 'Ingest Document URL'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
};
