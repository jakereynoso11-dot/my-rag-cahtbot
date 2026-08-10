import { useEffect, useState } from "react";
import * as api from "../api";
import CreateChatbotModal from "./CreateChatbotModal";

export default function ChatbotsList({ onOpen }) {
  const [chatbots, setChatbots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setChatbots(await api.listChatbots());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreateSubmit(name, purpose) {
    const chatbot = await api.createChatbot(name, purpose);
    setShowCreate(false);
    onOpen(chatbot);
  }

  async function handleRename(id) {
    const name = renameValue.trim();
    setRenamingId(null);
    if (!name) return;
    try {
      await api.renameChatbot(id, name);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(id, name, e) {
    e.stopPropagation();
    if (!window.confirm(`Delete "${name}"? This can't be undone.`)) return;
    try {
      await api.deleteChatbot(id);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="chatbots-page">
      <div className="chatbots-page-header">
        <h2>My Chatbots</h2>
        <button className="primary-button" onClick={() => setShowCreate(true)}>
          + Create Chatbot
        </button>
      </div>

      {error && <p className="error-text">{error}</p>}

      {loading ? (
        <p className="empty-text">Loading...</p>
      ) : chatbots.length === 0 ? (
        <div className="chatbots-empty">
          <p>You haven't created any chatbots yet.</p>
          <button className="primary-button" onClick={() => setShowCreate(true)}>
            Create your first chatbot
          </button>
        </div>
      ) : (
        <table className="chatbots-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Purpose</th>
              <th>Created</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {chatbots.map((c) => (
              <tr key={c.id} className="chatbots-table-row" onClick={() => onOpen(c)}>
                <td>
                  {renamingId === c.id ? (
                    <input
                      className="rename-input"
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      onBlur={() => handleRename(c.id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleRename(c.id);
                        if (e.key === "Escape") setRenamingId(null);
                      }}
                      autoFocus
                    />
                  ) : (
                    c.name
                  )}
                </td>
                <td className="chatbots-table-purpose">
                  {c.system_prompt || <span className="empty-text">No purpose set</span>}
                </td>
                <td>{new Date(c.created_at).toLocaleDateString()}</td>
                <td className="chatbots-table-actions">
                  <button
                    className="icon-button"
                    title="Rename"
                    onClick={(e) => {
                      e.stopPropagation();
                      setRenamingId(c.id);
                      setRenameValue(c.name);
                    }}
                  >
                    ✎
                  </button>
                  <button
                    className="icon-button"
                    title="Delete"
                    onClick={(e) => handleDelete(c.id, c.name, e)}
                  >
                    ×
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {showCreate && (
        <CreateChatbotModal onClose={() => setShowCreate(false)} onSubmit={handleCreateSubmit} />
      )}
    </div>
  );
}
