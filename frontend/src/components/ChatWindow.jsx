import { useEffect, useRef, useState } from "react";
import { apiFetch, deleteChatSession } from "../api";

export default function ChatWindow({ chatbotId }) {
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

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

  useEffect(() => {
    setSessionId(null);
    setMessages([]);
    setError("");
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
  }

  async function openSession(id) {
    setSessionId(id);
    setError("");
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
      }
      setSessions((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      setError(err.message);
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
      setMessages((prev) => [...prev, { role: "assistant", content: data.answer }]);
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
              <span className="session-title">{s.title || "Untitled conversation"}</span>
              <button
                className="icon-button session-delete-button"
                title="Delete conversation"
                onClick={(e) => handleDeleteSession(s.id, e)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      </aside>
      <div className="chat-window">
        <div className="chat-messages">
          {messages.length === 0 && (
            <p className="empty-text">Ask a question about your uploaded documents.</p>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`chat-bubble chat-bubble-${m.role}${m.isError ? " chat-bubble-error" : ""}`}
            >
              {m.content}
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
