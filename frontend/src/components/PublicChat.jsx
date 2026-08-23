import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import * as api from "../api";
import { citationLabel, rehypeCitationMarkers } from "../citations";

function sessionStorageKey(shareToken) {
  return `public_chat_session_${shareToken}`;
}

export default function PublicChat({ shareToken }) {
  const [chatbot, setChatbot] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [sessionId, setSessionId] = useState(() =>
    localStorage.getItem(sessionStorageKey(shareToken))
  );
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    api
      .getPublicChatbot(shareToken)
      .then(setChatbot)
      .catch((err) => setLoadError(err.message));
  }, [shareToken]);

  useEffect(() => {
    if (!sessionId) return;
    api
      .listPublicChatMessages(shareToken, sessionId)
      .then((rows) =>
        setMessages(rows.map((m) => ({ role: m.role, content: m.content })))
      )
      .catch(() => {
        // The saved session no longer exists (e.g. deleted) -- fall back to
        // a fresh one instead of leaving the page stuck on an error.
        localStorage.removeItem(sessionStorageKey(shareToken));
        setSessionId(null);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function handleRestart() {
    localStorage.removeItem(sessionStorageKey(shareToken));
    setSessionId(null);
    setMessages([]);
    setError("");
  }

  async function handleSend(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setSending(true);
    setError("");

    try {
      const data = await api.sendPublicChatMessage(shareToken, text, sessionId);
      localStorage.setItem(sessionStorageKey(shareToken), data.session_id);
      setSessionId(data.session_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          sources: data.sources,
          specialistName: data.specialist_name,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: err.message, isError: true },
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

  if (loadError) {
    return (
      <div className="public-chat-page public-chat-error">
        <p>{loadError}</p>
      </div>
    );
  }

  return (
    <div className="public-chat-page">
      <header className="public-chat-header">
        <span className="public-chat-title">{chatbot?.name || "Chat"}</span>
        <button className="link-button" onClick={handleRestart}>
          Restart
        </button>
      </header>
      <div className="chat-window">
        <div className="chat-messages">
          {messages.length === 0 && (
            <p className="empty-text">
              {chatbot?.purpose || "Ask a question to get started."}
            </p>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`chat-bubble chat-bubble-${m.role}${m.isError ? " chat-bubble-error" : ""}`}
            >
              {m.specialistName && (
                <span className="chat-specialist-badge">{m.specialistName}</span>
              )}
              {m.isError ? (
                m.content
              ) : (
                <div className="chat-markdown">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkBreaks]}
                    rehypePlugins={[rehypeCitationMarkers]}
                  >
                    {m.content}
                  </ReactMarkdown>
                </div>
              )}
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
          <button type="submit" disabled={sending || !input.trim()}>
            {sending ? "..." : "Send"}
          </button>
        </form>
      </div>
    </div>
  );
}
