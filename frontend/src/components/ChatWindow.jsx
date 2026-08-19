import { useEffect, useRef, useState } from "react";
import { apiFetch, deleteChatSession } from "../api";
import * as api from "../api";
import { citationLabel, renderCitedText } from "../citations";

export default function ChatWindow({ chatbotId }) {
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [renamingSessionId, setRenamingSessionId] = useState(null);
  const [renameValue, setRenameValue] = useState("");
  const [sessionDocuments, setSessionDocuments] = useState([]);
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const bottomRef = useRef(null);
  const sessionFileInputRef = useRef(null);

  async function loadSessions() {
    try {
      const resp = await apiFetch(
        `/chat/sessions?chatbot_id=${encodeURIComponent(chatbotId)}`
      );
      if (!resp.ok) return;
      setSessions(await resp.json());
    } catch {
      // Session list is a convenience; a failure here shouldn't block chat.
    }
  }

  async function loadSessionDocuments(id) {
    if (!id) {
      setSessionDocuments([]);
      return;
    }
    try {
      setSessionDocuments(await api.listSessionDocuments(id));
    } catch {
      // Non-critical; leave whatever was already shown.
    }
  }

  useEffect(() => {
    setSessionId(null);
    setMessages([]);
    setError("");
    setSessionDocuments([]);
    if (chatbotId) {
      loadSessions();
    } else {
      setSessions([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatbotId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function startNewChat() {
    setSessionId(null);
    setMessages([]);
    setError("");
    setSessionDocuments([]);
  }

  async function openSession(id) {
    setSessionId(id);
    setError("");
    loadSessionDocuments(id);
    try {
      const resp = await apiFetch(`/chat/sessions/${id}/messages`);
      if (!resp.ok) throw new Error("Could not load conversation");
      const rows = await resp.json();
      setMessages(rows.map((r) => ({ role: r.role, content: r.content })));
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDeleteSession(id, e) {
    e.stopPropagation();
    if (!window.confirm("Delete this conversation? This can't be undone.")) return;
    try {
      await deleteChatSession(id);
      if (id === sessionId) {
        setSessionId(null);
        setMessages([]);
        setSessionDocuments([]);
      }
      setSessions((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleRenameSession(id) {
    const title = renameValue.trim();
    setRenamingSessionId(null);
    if (!title) return;
    try {
      await api.renameChatSession(id, title);
      setSessions((prev) => prev.map((s) => (s.id === id ? { ...s, title } : s)));
    } catch (err) {
      setError(err.message);
    }
  }

  async function ensureSessionExists() {
    if (sessionId) return sessionId;
    const session = await api.createChatSession(chatbotId);
    setSessionId(session.id);
    await loadSessions();
    return session.id;
  }

  async function handleSessionFileChange(e) {
    const file = e.target.files[0];
    if (!file || !chatbotId) return;
    setUploadingDoc(true);
    setError("");
    try {
      const id = await ensureSessionExists();
      await api.uploadSessionDocument(id, file);
      await loadSessionDocuments(id);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploadingDoc(false);
      if (sessionFileInputRef.current) sessionFileInputRef.current.value = "";
    }
  }

  async function handleSend(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending || !chatbotId) return;

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setSending(true);
    setError("");

    try {
      const resp = await apiFetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chatbot_id: chatbotId, message: text, session_id: sessionId }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "Chat request failed");

      const isNewSession = !sessionId;
      setSessionId(data.session_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          specialistName: data.specialist_name,
          sources: data.sources,
        },
      ]);
      if (isNewSession) loadSessions();
    } catch (err) {
      setError(err.message);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${err.message}`, isError: true },
      ]);
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend(e);
    }
  }

  return (
    <section className="chat-area">
      <aside className="sessions-panel">
        <button className="new-chat-button" onClick={startNewChat}>
          + New chat
        </button>
        <ul className="sessions-list">
          {sessions.map((s) => (
            <li
              key={s.id}
              className={s.id === sessionId ? "session-item active" : "session-item"}
              onClick={() => openSession(s.id)}
            >
              {renamingSessionId === s.id ? (
                <input
                  className="session-rename-input"
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                  onBlur={() => handleRenameSession(s.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleRenameSession(s.id);
                    if (e.key === "Escape") setRenamingSessionId(null);
                  }}
                  autoFocus
                />
              ) : (
                <>
                  <span className="session-title" title={s.title || "Untitled conversation"}>
                    {s.title || "Untitled conversation"}
                  </span>
                  <span className="session-actions">
                    <button
                      className="icon-button session-delete-button"
                      title="Rename conversation"
                      onClick={(e) => {
                        e.stopPropagation();
                        setRenamingSessionId(s.id);
                        setRenameValue(s.title || "");
                      }}
                    >
                      ✎
                    </button>
                    <button
                      className="icon-button session-delete-button"
                      title="Delete conversation"
                      onClick={(e) => handleDeleteSession(s.id, e)}
                    >
                      ×
                    </button>
                  </span>
                </>
              )}
            </li>
          ))}
        </ul>
      </aside>
      <div className="chat-window">
        {chatbotId && (
          <div className="session-documents">
            <div className="session-documents-header">
              <span>This conversation's documents</span>
              <label className="session-documents-upload">
                {uploadingDoc ? "Uploading..." : "+ Attach file"}
                <input
                  ref={sessionFileInputRef}
                  type="file"
                  accept="application/pdf"
                  onChange={handleSessionFileChange}
                  disabled={uploadingDoc}
                  hidden
                />
              </label>
            </div>
            {sessionDocuments.length > 0 && (
              <ul className="session-documents-list">
                {sessionDocuments.map((doc) => (
                  <li key={doc.id} className="session-document-chip">
                    {doc.display_name || doc.documents?.original_filename}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        <div className="chat-messages">
          {messages.length === 0 && (
            <p className="empty-text">Ask a question about your uploaded documents.</p>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`chat-bubble chat-bubble-${m.role}${m.isError ? " chat-bubble-error" : ""}`}
            >
              {m.specialistName && (
                <span className="chat-specialist-badge">{m.specialistName}</span>
              )}
              {renderCitedText(m.content)}
              {m.sources && m.sources.length > 0 && (
                <ul className="citation-list">
                  {m.sources.map((src, idx) => (
                    <li key={idx}>
                      <span className="citation-index">[{idx + 1}]</span>
                      <span className="citation-name">{citationLabel(src, idx)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
        {error && <p className="error-text">{error}</p>}
        <form className="chat-input-row" onSubmit={handleSend}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask something..."
            rows={1}
          />
          <button type="submit" disabled={sending || !input.trim() || !chatbotId}>
            {sending ? "..." : "Send"}
          </button>
        </form>
      </div>
    </section>
  );
}
