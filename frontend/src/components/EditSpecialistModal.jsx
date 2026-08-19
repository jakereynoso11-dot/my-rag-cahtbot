import { useState } from "react";
import * as api from "../api";

export default function EditSpecialistModal({ chatbotId, specialist, onClose, onSaved }) {
  const [name, setName] = useState(specialist.name || "");
  const [specialty, setSpecialty] = useState(specialist.specialty || "");
  const [instructions, setInstructions] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    const trimmedName = name.trim();
    const trimmedSpecialty = specialty.trim();
    if (!trimmedName || !trimmedSpecialty) {
      setError("Give the specialist a name and what it specializes in.");
      return;
    }
    setError("");
    setSaving(true);
    try {
      const updated = await api.updateSpecialist(chatbotId, specialist.id, {
        name: trimmedName,
        specialty: trimmedSpecialty,
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
        <h2>Edit specialist</h2>
        <form className="modal-form" onSubmit={handleSubmit}>
          <label htmlFor="edit-specialist-name">Name</label>
          <input
            id="edit-specialist-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
            required
          />

          <label htmlFor="edit-specialist-specialty">Specializes in</label>
          <input
            id="edit-specialist-specialty"
            type="text"
            value={specialty}
            onChange={(e) => setSpecialty(e.target.value)}
            required
          />

          <label htmlFor="edit-specialist-instructions">
            Instructions <span className="agent-create-optional">(leave blank to keep as-is)</span>
          </label>
          <textarea
            id="edit-specialist-instructions"
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            rows={2}
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
