import { useState } from "react";
import * as api from "../api";

export default function EditChatbotModal({ chatbot, onClose, onSaved }) {
  const [name, setName] = useState(chatbot.name || "");
  const [purpose, setPurpose] = useState(chatbot.purpose || "");
  const [instructions, setInstructions] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError("Give your chatbot a name.");
      return;
    }
    setError("");
    setSaving(true);
    try {
      const updated = await api.updateChatbot(chatbot.id, {
        name: trimmedName,
        purpose: purpose.trim(),
        ...(instructions.trim() ? { systemPrompt: instructions.trim() } : {}),
      });
      onSaved(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h2>Edit chatbot</h2>
        <form className="modal-form" onSubmit={handleSubmit}>
          <label htmlFor="edit-chatbot-name">Name</label>
          <input
            id="edit-chatbot-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
            required
          />

          <label htmlFor="edit-chatbot-purpose">Purpose</label>
          <textarea
            id="edit-chatbot-purpose"
            value={purpose}
            onChange={(e) => setPurpose(e.target.value)}
            rows={2}
          />

          <label htmlFor="edit-chatbot-instructions">
            Instructions <span className="agent-create-optional">(leave blank to keep as-is)</span>
          </label>
          <textarea
            id="edit-chatbot-instructions"
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            rows={3}
            placeholder="How should it behave?"
          />

          {error && <p className="error-text">{error}</p>}

          <div className="modal-actions">
            <button type="submit" disabled={saving}>
              {saving ? "Saving..." : "Save changes"}
            </button>
            <button type="button" className="link-button" onClick={onClose}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
