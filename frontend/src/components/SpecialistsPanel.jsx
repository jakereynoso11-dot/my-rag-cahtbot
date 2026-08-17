import { useEffect, useState } from "react";
import * as api from "../api";

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
    try {
      await api.createSpecialist(chatbotId, name, specialty, newPrompt.trim());
      resetCreateForm();
      await loadSpecialists();
    } catch (err) {
      setCreateError(err.message);
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
        documents later if you add any.
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

      {error && <p className="error-text">{error}</p>}

      {loading ? (
        <p className="empty-text">Loading...</p>
      ) : specialists.length === 0 ? (
        <p className="empty-text">No specialists yet.</p>
      ) : (
        <ul className="specialists-list">
          {specialists.map((s) => (
            <li key={s.id} className="specialist-item">
              <span className="specialist-info">
                <span className="specialist-name">{s.name}</span>
                <span className="specialist-specialty">{s.specialty}</span>
              </span>
              <button
                className="icon-button"
                title="Delete"
                onClick={() => handleDelete(s.id, s.name)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
