import React from 'react';
import { FileText, Image as ImageIcon, X, Loader2, ChevronRight, Paperclip } from 'lucide-react';

/**
 * AttachmentsPanel
 *
 * Right-side drawer that shows all attachments for the current conversation:
 *  - Ingested documents (persistent across conversation)
 *  - Images that have already been sent in past messages (read-only, historical)
 *
 * Props:
 *   isOpen          {bool}     - Whether the panel is visible
 *   onClose         {fn}       - Close button handler
 *   activeFiles     {object[]} - [{ name: string }] — ingested docs in conv
 *   sentImages      {string[]} - Base64 data URIs from sent messages (read-only)
 *   ingesting       {bool}     - True while a doc is uploading
 *   uploadingFileName {string} - Name of the file being uploaded
 *   onRemoveFile    {fn}       - (index) => void — remove doc pill
 */
export const AttachmentsPanel = ({
  isOpen,
  onClose,
  activeFiles = [],
  sentImages = [],
  ingesting = false,
  uploadingFileName = '',
  onRemoveFile,
}) => {
  const hasContent = activeFiles.length > 0 || sentImages.length > 0 || ingesting;

  return (
    <>
      {/* Backdrop for mobile */}
      {isOpen && (
        <div
          className="attachments-backdrop"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside className={`attachments-panel${isOpen ? ' open' : ''}`} aria-label="Attachments">

        {/* ── Header ── */}
        <div className="attachments-panel-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Paperclip size={15} style={{ color: 'var(--primary)' }} />
            <span style={{ fontWeight: 700, fontSize: '0.88rem', color: 'var(--text-main)' }}>
              Attachments
            </span>
          </div>
          <button
            className="attachments-close-btn"
            onClick={onClose}
            title="Close panel"
            aria-label="Close attachments panel"
          >
            <ChevronRight size={17} />
          </button>
        </div>

        {/* ── Body ── */}
        <div className="attachments-panel-body">

          {/* Upload in progress */}
          {ingesting && uploadingFileName && (
            <div className="attachments-section">
              <p className="attachments-section-label">Uploading</p>
              <div className="attachment-uploading-pill">
                <Loader2 size={13} style={{ animation: 'spin 1s linear infinite', flexShrink: 0 }} />
                <span className="attachment-filename">{uploadingFileName}</span>
              </div>
            </div>
          )}

          {/* Ingested documents */}
          {activeFiles.length > 0 && (
            <div className="attachments-section">
              <p className="attachments-section-label">
                Documents
                <span className="attachments-count">{activeFiles.length}</span>
              </p>
              <div className="attachments-list">
                {activeFiles.map((f, i) => (
                  <div key={i} className="attachment-doc-item">
                    <FileText size={14} style={{ color: 'var(--accent-emerald)', flexShrink: 0 }} />
                    <span className="attachment-filename" title={f.name}>{f.name}</span>
                    {onRemoveFile && (
                      <button
                        className="attachment-remove-btn"
                        onClick={() => onRemoveFile(i)}
                        title="Remove from context"
                        aria-label={`Remove ${f.name}`}
                      >
                        <X size={11} />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Images already sent in the conversation (read-only, historical) */}
          {sentImages.length > 0 && (
            <div className="attachments-section">
              <p className="attachments-section-label">
                Images sent
                <span className="attachments-count">{sentImages.length}</span>
              </p>
              <div className="attachments-image-grid">
                {sentImages.map((b64, idx) => (
                  <div key={idx} className="attachment-image-thumb">
                    <img src={b64} alt={`Sent image ${idx + 1}`} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Empty state */}
          {!hasContent && (
            <div className="attachments-empty">
              <ImageIcon size={28} style={{ color: 'var(--text-dim)', marginBottom: '10px' }} />
              <p>No attachments yet</p>
              <p style={{ fontSize: '0.78rem', marginTop: '4px' }}>
                Upload a document or image using the <strong>+</strong> button in the chat.
              </p>
            </div>
          )}
        </div>
      </aside>
    </>
  );
};
