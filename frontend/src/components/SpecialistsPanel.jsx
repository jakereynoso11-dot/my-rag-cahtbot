import { useEffect, useRef, useState } from "react";
import * as api from "../api";
import CreateSpecialistModal from "./CreateSpecialistModal";
import CreationProgressModal from "./CreationProgressModal";
import EditSpecialistModal from "./EditSpecialistModal";

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
  const [submitting, setSubmitting] = useState(false);
  const [creationProgressError, setCreationProgressError] = useState("");
  const [expandedId, setExpandedId] = useState(null);
  const [editingSpecialist, setEditingSpecialist] = useState(null);

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

  async function handleCreate({ name, specialty, instructions }) {
    setCreating(false);
    setSubmitting(true);
    setCreationProgressError("");
    try {
      await api.createSpecialist(chatbotId, name, specialty, instructions);
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
    <aside className="specialists-panel" data-tour="specialists-panel">
      <div className="specialists-panel-header">
        <h2>Specialists</h2>
        <button className="icon-button" onClick={() => setCreating(true)} title="Add a specialist">
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
        <CreateSpecialistModal onClose={() => setCreating(false)} onSubmit={handleCreate} />
      )}

      {(submitting || creationProgressError) && (
        <CreationProgressModal
          label="Adding specialist..."
          error={creationProgressError}
          onDismissError={() => setCreationProgressError("")}
        />
      )}

      {editingSpecialist && (
        <EditSpecialistModal
          chatbotId={chatbotId}
          specialist={editingSpecialist}
          onClose={() => setEditingSpecialist(null)}
          onSaved={() => {
            setEditingSpecialist(null);
            loadSpecialists();
          }}
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
                <span className="specialist-actions">
                  <button
                    className="icon-button"
                    title="Edit"
                    onClick={(e) => {
                      e.stopPropagation();
                      setEditingSpecialist(s);
                    }}
                  >
                    ✎
                  </button>
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
                </span>
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
