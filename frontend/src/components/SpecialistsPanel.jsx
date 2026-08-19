import { useEffect, useRef, useState } from "react";
import * as api from "../api";
import CreationProgressModal from "./CreationProgressModal";

function SpecialistDocuments({ chatbotId, specialistId }) {
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);

  async function load() {
    try {
      setDocuments(await api.listSpecialistDocuments(chatbotId, specialistId));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [specialistId]);

  async function handleFileChange(e) {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      await api.uploadSpecialistDocument(chatbotId, specialistId, file);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <div className="session-documents">
      <div className="session-documents-header">
        <span>This specialist's own documents</span>
        <label className="session-documents-upload">
          {uploading ? "Uploading..." : "+ Attach file"}
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            onChange={handleFileChange}
            disabled={uploading}
            hidden
          />
        </label>
      </div>
      {error && <p className="error-text">{error}</p>}
      {documents.length > 0 && (
        <ul className="session-documents-list">
          {documents.map((doc) => (
            <li key={doc.id} className="session-document-chip">
              {doc.display_name || doc.documents?.original_filename}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function SpecialistsPanel({ chatbotId }) {
  const [specialists, setSpecialists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSpecialty, setNewSpecialty] = useState("");
  const [newPrompt, setNewPrompt] = useState("");
  const [creationProgressError, setCreationProgressError] = useState("");
  const [expandedId, setExpandedId] = useState(null);

  async function loadSpecialists() {
    setLoading(true);
    setError("");
    try {
      setSpecialists(await api.listSpecialists(chatbotId));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setSpecialists([]);
    setError("");
    setExpandedId(null);
    if (chatbotId) loadSpecialists();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatbotId]);

  function resetCreateForm() {
    setNewName("");
    setNewSpecialty("");
    setNewPrompt("");
    setCreateError("");
    setCreating(false);
  }

  async function handleCreate(e) {
    e.preventDefault();
    const name = newName.trim();
    const specialty = newSpecialty.trim();
    if (!name || !specialty) {
      setCreateError("Give the specialist a name and what it specializes in.");
      return;
    }
    setCreateError("");
    setSubmitting(true);
    setCreationProgressError("");
    try {
      await api.createSpecialist(chatbotId, name, specialty, newPrompt.trim());
      resetCreateForm();
      await loadSpecialists();
    } catch (err) {
      setCreationProgressError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id, name) {
    if (!window.confirm(`Delete "${name}"? This can't be undone.`)) return;
    try {
      await api.deleteSpecialist(chatbotId, id);
      await loadSpecialists();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <aside className="specialists-panel">
      <div className="specialists-panel-header">
        <h2>Specialists</h2>
        <button
          className="icon-button"
          onClick={() => (creating ? resetCreateForm() : setCreating(true))}
          title="Add a specialist"
        >
          + New
        </button>
      </div>
      <p className="specialists-panel-hint">
        Optional. Add specialists for specific topics (e.g. "Billing") and this
        chatbot will automatically hand off matching questions to them. No
        documents required — a specialist works right away and can pick up
        documents later if you add any. Give a specialist its own documents
        (click it to expand) and routing uses them to pick the best match.
      </p>

      {creating && (
        <form className="specialist-create-form" onSubmit={handleCreate}>
          <input
            type="text"
            placeholder='Name, e.g. "Billing Agent"'
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            autoFocus
            required
          />
          <input
            type="text"
            placeholder='Specializes in, e.g. "billing and invoice questions"'
            value={newSpecialty}
            onChange={(e) => setNewSpecialty(e.target.value)}
            required
          />
          <textarea
            placeholder='Extra instructions (optional), e.g. "Keep answers short and always mention the relevant policy number."'
            value={newPrompt}
            onChange={(e) => setNewPrompt(e.target.value)}
            rows={2}
          />
          {createError && <p className="error-text">{createError}</p>}
          <div className="specialist-create-actions">
            <button type="submit" disabled={submitting}>
              {submitting ? "Adding..." : "Add specialist"}
            </button>
            <button type="button" className="link-button" onClick={resetCreateForm}>
              Cancel
            </button>
          </div>
        </form>
      )}

      {(submitting || creationProgressError) && (
        <CreationProgressModal
          label="Adding specialist..."
          error={creationProgressError}
          onDismissError={() => setCreationProgressError("")}
        />
      )}

      {error && <p className="error-text">{error}</p>}

      {loading ? (
        <p className="empty-text">Loading...</p>
      ) : specialists.length === 0 ? (
        <p className="empty-text">No specialists yet.</p>
      ) : (
        <ul className="specialists-list">
          {specialists.map((s) => (
            <li key={s.id} className="specialist-item-wrapper">
              <div
                className="specialist-item"
                onClick={() => setExpandedId(expandedId === s.id ? null : s.id)}
              >
                <span className="specialist-info">
                  <span className="specialist-name">{s.name}</span>
                  <span className="specialist-specialty">{s.specialty}</span>
                </span>
                <button
                  className="icon-button"
                  title="Delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(s.id, s.name);
                  }}
                >
                  ×
                </button>
              </div>
              {expandedId === s.id && (
                <SpecialistDocuments chatbotId={chatbotId} specialistId={s.id} />
              )}
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
