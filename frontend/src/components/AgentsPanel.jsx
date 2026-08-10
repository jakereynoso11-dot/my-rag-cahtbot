import { useEffect, useState } from "react";
import * as api from "../api";

export default function AgentsPanel({ selectedId, onSelect }) {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPurpose, setNewPurpose] = useState("");
  const [newPrompt, setNewPrompt] = useState("");
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState("");

  async function loadAgents(selectAfterId) {
    setLoading(true);
    setError("");
    try {
      const rows = await api.listChatbots();
      setAgents(rows);
      if (selectAfterId) {
        onSelect(selectAfterId);
      } else if (!rows.some((r) => r.id === selectedId)) {
        onSelect(rows[0]?.id ?? null);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAgents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function resetCreateForm() {
    setNewName("");
    setNewPurpose("");
    setNewPrompt("");
    setCreateError("");
    setCreating(false);
  }

  async function handleCreate(e) {
    e.preventDefault();
    const name = newName.trim();
    const purpose = newPurpose.trim();
    if (!name) {
      setCreateError("Give your agent a name.");
      return;
    }
    if (!purpose) {
      setCreateError("Describe what this agent is for — it helps it stay on topic.");
      return;
    }
    setCreateError("");
    setSubmitting(true);
    try {
      const agent = await api.createChatbot(name, purpose, newPrompt.trim());
      resetCreateForm();
      await loadAgents(agent.id);
    } catch (err) {
      setCreateError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRename(id) {
    const name = renameValue.trim();
    setRenamingId(null);
    if (!name) return;
    try {
      await api.renameChatbot(id, name);
      await loadAgents();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(id, name) {
    if (!window.confirm(`Delete "${name}"? This can't be undone.`)) return;
    try {
      await api.deleteChatbot(id);
      await loadAgents();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <aside className="agents-panel" data-tour="agents-panel">
      <div className="agents-panel-header">
        <h2>Your Agents</h2>
        <button
          className="icon-button"
          onClick={() => (creating ? resetCreateForm() : setCreating(true))}
          title="Create a new agent"
        >
          + New
        </button>
      </div>

      {creating && (
        <form className="agent-create-form" onSubmit={handleCreate}>
          <label className="agent-create-label" htmlFor="agent-create-name">
            Name
          </label>
          <input
            id="agent-create-name"
            type="text"
            placeholder='e.g. "Tax Docs Helper"'
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            autoFocus
            required
          />

          <label className="agent-create-label" htmlFor="agent-create-purpose">
            Purpose
          </label>
          <textarea
            id="agent-create-purpose"
            placeholder="What is this agent for? e.g. &quot;Answer questions about my uploaded tax documents so I don't have to dig through them myself.&quot;"
            value={newPurpose}
            onChange={(e) => setNewPurpose(e.target.value)}
            rows={2}
            required
          />

          <label className="agent-create-label" htmlFor="agent-create-instructions">
            Instructions <span className="agent-create-optional">(optional)</span>
          </label>
          <textarea
            id="agent-create-instructions"
            placeholder='How should it behave? e.g. "Only answer from the uploaded documents. Keep answers short. If unsure, say so rather than guessing."'
            value={newPrompt}
            onChange={(e) => setNewPrompt(e.target.value)}
            rows={3}
          />

          {createError && <p className="error-text">{createError}</p>}

          <div className="agent-create-actions">
            <button type="submit" disabled={submitting}>
              {submitting ? "Creating..." : "Create agent"}
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
      ) : agents.length === 0 ? (
        <p className="empty-text">No agents yet. Create one to get started.</p>
      ) : (
        <ul className="agents-list">
          {agents.map((a) => (
            <li key={a.id} className={a.id === selectedId ? "agent-item active" : "agent-item"}>
              {renamingId === a.id ? (
                <input
                  className="agent-rename-input"
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                  onBlur={() => handleRename(a.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleRename(a.id);
                    if (e.key === "Escape") setRenamingId(null);
                  }}
                  autoFocus
                />
              ) : (
                <>
                  <span className="agent-name-block" onClick={() => onSelect(a.id)}>
                    <span className="agent-name">{a.name}</span>
                    {a.purpose && <span className="agent-purpose">{a.purpose}</span>}
                  </span>
                  <span className="agent-actions">
                    <button
                      className="icon-button"
                      title="Rename"
                      onClick={() => {
                        setRenamingId(a.id);
                        setRenameValue(a.name);
                      }}
                    >
                      ✎
                    </button>
                    <button
                      className="icon-button"
                      title="Delete"
                      onClick={() => handleDelete(a.id, a.name)}
                    >
                      ×
                    </button>
                  </span>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
