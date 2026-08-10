import { useState } from "react";

export default function CreateChatbotModal({ onClose, onSubmit }) {
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) return;
    setSubmitting(true);
    setError("");
    try {
      await onSubmit(trimmedName, purpose.trim());
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form className="modal-card" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
        <h2>Create a new chatbot</h2>
        <label>
          Name
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Tax Docs Helper"
            autoFocus
            required
          />
        </label>
        <label>
          Purpose
          <textarea
            value={purpose}
            onChange={(e) => setPurpose(e.target.value)}
            placeholder={
              'What should this chatbot do? e.g. "Answer questions about our tax filing ' +
              'documents, and say so if the answer isn\'t in them."'
            }
            rows={4}
          />
        </label>
        {error && <p className="error-text">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="link-button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="primary-button" disabled={submitting || !name.trim()}>
            {submitting ? "Creating..." : "Create chatbot"}
          </button>
        </div>
      </form>
    </div>
  );
}
