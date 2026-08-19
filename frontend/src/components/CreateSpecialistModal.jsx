import { useState } from "react";

export default function CreateSpecialistModal({ onClose, onSubmit }) {
  const [name, setName] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [instructions, setInstructions] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    const trimmedName = name.trim();
    const trimmedSpecialty = specialty.trim();
    if (!trimmedName || !trimmedSpecialty) {
      setError("Give the specialist a name and what it specializes in.");
      return;
    }
    setError("");
    onSubmit({ name: trimmedName, specialty: trimmedSpecialty, instructions: instructions.trim() });
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h2>Add a specialist</h2>
        <form className="modal-form" onSubmit={handleSubmit}>
          <label htmlFor="create-specialist-name">Name</label>
          <input
            id="create-specialist-name"
            type="text"
            placeholder='e.g. "Billing Agent"'
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
            required
          />

          <label htmlFor="create-specialist-specialty">Specializes in</label>
          <input
            id="create-specialist-specialty"
            type="text"
            placeholder='e.g. "billing and invoice questions"'
            value={specialty}
            onChange={(e) => setSpecialty(e.target.value)}
            required
          />

          <label htmlFor="create-specialist-instructions">
            Instructions <span className="agent-create-optional">(optional)</span>
          </label>
          <textarea
            id="create-specialist-instructions"
            placeholder='e.g. "Keep answers short and always mention the relevant policy number."'
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            rows={4}
          />

          {error && <p className="error-text">{error}</p>}

          <div className="modal-actions">
            <button type="submit">Add specialist</button>
            <button type="button" className="link-button" onClick={onClose}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
