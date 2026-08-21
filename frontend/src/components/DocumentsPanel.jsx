import { useEffect, useRef, useState } from "react";
import { apiFetch } from "../api";
import * as api from "../api";

export default function DocumentsPanel({ chatbotId }) {
  const [documents, setDocuments] = useState([]);
  const [specialists, setSpecialists] = useState([]);
  const [targetSpecialistId, setTargetSpecialistId] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);

  async function loadDocuments() {
    try {
      const resp = await apiFetch(`/documents?chatbot_id=${encodeURIComponent(chatbotId)}`);
      if (!resp.ok) throw new Error("Could not load documents");
      setDocuments(await resp.json());
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadSpecialists() {
    try {
      setSpecialists(await api.listSpecialists(chatbotId));
    } catch {
      setSpecialists([]);
    }
  }

  useEffect(() => {
    setDocuments([]);
    setSpecialists([]);
    setTargetSpecialistId("");
    setError("");
    if (chatbotId) {
      loadDocuments();
      loadSpecialists();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatbotId]);

  async function handleFileChange(e) {
    const file = e.target.files[0];
    if (!file || !chatbotId) return;
    setUploading(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("chatbot_id", chatbotId);
      formData.append("file", file);
      if (targetSpecialistId) formData.append("specialist_id", targetSpecialistId);
      const resp = await apiFetch("/ingest/file", { method: "POST", body: formData });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || "Upload failed");
      }
      await loadDocuments();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <aside className="documents-panel">
      <h2>Documents</h2>
      {specialists.length > 0 && (
        <select
          className="doc-target-select"
          value={targetSpecialistId}
          onChange={(e) => setTargetSpecialistId(e.target.value)}
          disabled={uploading}
        >
          <option value="">Shared with all specialists</option>
          {specialists.map((s) => (
            <option key={s.id} value={s.id}>
              Only {s.name}
            </option>
          ))}
        </select>
      )}
      <label className="upload-dropzone">
        {uploading ? "Uploading..." : "Drop files or click to upload"}
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          onChange={handleFileChange}
          disabled={uploading}
          hidden
        />
      </label>
      {error && <p className="error-text">{error}</p>}
      {documents.length === 0 ? (
        <p className="empty-text">No documents yet.</p>
      ) : (
        <ul className="documents-list">
          {documents.map((doc) => (
            <li key={doc.id}>
              <span className="doc-name">
                {doc.display_name || doc.documents?.original_filename}
              </span>
              <span className="doc-meta">
                <span className={`doc-status doc-status-${doc.documents?.index_status}`}>
                  {doc.documents?.index_status}
                </span>
                <span className="doc-scope">
                  {doc.specialist_id ? `Only ${doc.chatbot_specialists?.name}` : "Shared"}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
