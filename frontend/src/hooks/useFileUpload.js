import { useState, useRef } from 'react';
import { api } from '../services/api';

/**
 * useFileUpload
 *
 * Manages file ingestion state and the error messaging for upload failures.
 * Extracted from ChatWindow.jsx.
 *
 * @param {object} opts
 * @param {Function} opts.ensureActiveConversation - async fn that returns a conversation id
 * @param {Function} opts.setError - setter from the parent error state
 * @param {Function} opts.onRefreshConversations - called after successful upload
 */
export function useFileUpload({ ensureActiveConversation, setError, onRefreshConversations }) {
  const [ingesting, setIngesting] = useState(false);
  const [uploadingFileName, setUploadingFileName] = useState(null);
  const [activeFiles, setActiveFiles] = useState([]);
  const fileInputRef = useRef(null);

  const handleQuickFileSelect = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setIngesting(true);
    setUploadingFileName(file.name);
    setError(null);

    try {
      const activeId = await ensureActiveConversation();
      await api.ingestFile(file, activeId);
      setActiveFiles((prev) => [...prev, { name: file.name }]);
      if (onRefreshConversations) onRefreshConversations();
    } catch (err) {
      const msg = err.message || '';
      if (msg.includes('409') || msg.toLowerCase().includes('already been uploaded')) {
        setError(`'${file.name}' is already in this conversation. Try a different conversation or rename the file.`);
      } else if (msg.includes('413') || msg.toLowerCase().includes('too large')) {
        setError('File is too large. Please upload a smaller document (max ~10 MB).');
      } else if (msg.includes('422') || msg.toLowerCase().includes('readable text')) {
        setError(msg.length < 180 ? msg : 'The server could not extract readable text from this file. Try a text-based PDF or DOCX.');
      } else if (msg.includes('500')) {
        setError('The server encountered an error processing this file. Try a different format (PDF, DOCX, TXT).');
      } else {
        setError(msg || 'File upload failed. Please check the file and try again.');
      }
    } finally {
      setIngesting(false);
      setUploadingFileName(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const removeFile = (index) => {
    setActiveFiles((prev) => prev.filter((_, i) => i !== index));
  };

  return {
    ingesting,
    uploadingFileName,
    activeFiles,
    setActiveFiles,
    fileInputRef,
    handleQuickFileSelect,
    removeFile,
  };
}
