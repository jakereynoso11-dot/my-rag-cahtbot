import { useState } from "react";

export default function CreateChatbotModal({ onClose, onSubmit }) {
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState("");
  const [instructions, setInstructions] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    const trimmedName = name.trim();
    const trimmedPurpose = purpose.trim();
    if (!trimmedName) {
      setError("Give your chatbot a name.");
      return;
    }
    if (!trimmedPurpose) {
      setError("Describe what this chatbot is for — it helps it stay on topic.");
      return;
    }
    setError("");
    onSubmit({ name: trimmedName, purpose: trimmedPurpose, instructions: instructions.trim() });
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h2>Create a chatbot</h2>
        <form className="modal-form" onSubmit={handleSubmit}>
          <label htmlFor="create-chatbot-name">Name</label>
          <input
            id="create-chatbot-name"
            type="text"
            placeholder='e.g. "Tax Docs Helper"'
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
            required
          />

          <label htmlFor="create-chatbot-purpose">Purpose</label>
          <textarea
            id="create-chatbot-purpose"
            placeholder="What is this chatbot for? e.g. &quot;Answer questions about my uploaded tax documents so I don't have to dig through them myself.&quot;"
            value={purpose}
            onChange={(e) => setPurpose(e.target.value)}
            rows={2}
            required
          />

          <label htmlFor="create-chatbot-instructions">
            Instructions <span className="agent-create-optional">(optional)</span>
          </label>
          <textarea
            id="create-chatbot-instructions"
            placeholder='How should it behave? e.g. "Only answer from the uploaded documents. Keep answers short. If unsure, say so rather than guessing."'
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            rows={3}
          />

          {error && <p className="error-text">{error}</p>}

          <div className="modal-actions">
            <button type="submit">Create chatbot</button>
            <button type="button" className="link-button" onClick={onClose}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
