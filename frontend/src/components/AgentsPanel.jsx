import { useEffect, useState } from "react";
import * as api from "../api";

export default function AgentsPanel({ selectedId, onSelect }) {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
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

  async function handleCreate(e) {
    e.preventDefault();
    const name = newName.trim();
    if (!name) return;
    try {
      const agent = await api.createChatbot(name, newPrompt.trim());
      setNewName("");
      setNewPrompt("");
      setCreating(false);
      await loadAgents(agent.id);
    } catch (err) {
      setError(err.message);
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
          onClick={() => setCreating((v) => !v)}
          title="Create a new agent"
        >
          + New
        </button>
      </div>

      {creating && (
        <form className="agent-create-form" onSubmit={handleCreate}>
          <input
            type="text"
            placeholder="Agent name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            autoFocus
            required
          />
          <textarea
            placeholder={'Instructions (optional), e.g. "You\'re a tax assistant, only answer from the uploaded documents."'}
            value={newPrompt}
            onChange={(e) => setNewPrompt(e.target.value)}
            rows={3}
          />
          <div className="agent-create-actions">
            <button type="submit">Create</button>
            <button type="button" className="link-button" onClick={() => setCreating(false)}>
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
                  <span className="agent-name" onClick={() => onSelect(a.id)}>
                    {a.name}
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
