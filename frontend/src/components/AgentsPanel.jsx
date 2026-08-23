import { useEffect, useState } from "react";
import * as api from "../api";
import CreateChatbotModal from "./CreateChatbotModal";
import CreationProgressModal from "./CreationProgressModal";
import EditChatbotModal from "./EditChatbotModal";

export default function AgentsPanel({ selectedId, onSelect, onAgentsLoaded }) {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [creationProgressError, setCreationProgressError] = useState("");
  const [editingAgent, setEditingAgent] = useState(null);
  const [copiedId, setCopiedId] = useState(null);

  async function handleCopyShareLink(shareToken, id) {
    const url = `${window.location.origin}/chat/${shareToken}`;
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      window.prompt("Copy this link:", url);
      return;
    }
    setCopiedId(id);
    setTimeout(() => setCopiedId((current) => (current === id ? null : current)), 1500);
  }

  async function loadAgents(selectAfterId) {
    setLoading(true);
    setError("");
    try {
      const rows = await api.listChatbots();
      setAgents(rows);
      onAgentsLoaded?.(rows.length);
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

  async function handleCreate({ name, purpose, instructions }) {
    setCreating(false);
    setSubmitting(true);
    setCreationProgressError("");
    try {
      const agent = await api.createChatbot(name, purpose, instructions);
      await loadAgents(agent.id);
    } catch (err) {
      setCreationProgressError(err.message);
    } finally {
      setSubmitting(false);
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
        <h2>Your Chatbots</h2>
        <button className="icon-button" onClick={() => setCreating(true)} title="Create a new chatbot">
          + New
        </button>
      </div>

      {creating && (
        <CreateChatbotModal onClose={() => setCreating(false)} onSubmit={handleCreate} />
      )}

      {(submitting || creationProgressError) && (
        <CreationProgressModal
          label="Creating your chatbot..."
          error={creationProgressError}
          onDismissError={() => setCreationProgressError("")}
        />
      )}

      {editingAgent && (
        <EditChatbotModal
          chatbot={editingAgent}
          onClose={() => setEditingAgent(null)}
          onSaved={() => {
            setEditingAgent(null);
            loadAgents();
          }}
        />
      )}

      {error && <p className="error-text">{error}</p>}

      {loading ? (
        <p className="empty-text">Loading...</p>
      ) : agents.length === 0 ? (
        <p className="empty-text">No chatbots yet. Create one to get started.</p>
      ) : (
        <ul className="agents-list">
          {agents.map((a) => (
            <li key={a.id} className={a.id === selectedId ? "agent-item active" : "agent-item"}>
              <span className="agent-name-block" onClick={() => onSelect(a.id)}>
                <span className="agent-name">{a.name}</span>
                {a.purpose && <span className="agent-purpose">{a.purpose}</span>}
              </span>
              <span className="agent-actions">
                <button
                  className="icon-button"
                  title="Copy public chat link"
                  onClick={() => handleCopyShareLink(a.share_token, a.id)}
                >
                  {copiedId === a.id ? "✓" : "🔗"}
                </button>
                <button
                  className="icon-button"
                  title="Edit"
                  onClick={() => setEditingAgent(a)}
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
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
