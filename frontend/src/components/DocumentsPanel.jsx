import { useEffect, useRef, useState } from "react";
import { apiFetch } from "../api";

export default function DocumentsPanel({ chatbotId }) {
  const [documents, setDocuments] = useState([]);
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

  useEffect(() => {
    setDocuments([]);
    setError("");
    if (chatbotId) loadDocuments();
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
              <span className={`doc-status doc-status-${doc.documents?.index_status}`}>
                {doc.documents?.index_status}
              </span>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
