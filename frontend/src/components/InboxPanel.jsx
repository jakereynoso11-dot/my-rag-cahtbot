import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import * as api from "../api";

function timeAgo(iso) {
  if (!iso) return "";
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffMin = Math.round(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  if (diffDay < 30) return `${diffDay}d ago`;
  return new Date(iso).toLocaleDateString();
}

// Admin-facing view of every visitor conversation across the user's
// chatbots -- separate from ChatWindow, which is the owner's own test chat
// against a single selected chatbot.
export default function InboxPanel({ onUnreadCountChange, openSessionId, onOpenSessionHandled }) {
  const [chatbots, setChatbots] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [chatbotFilter, setChatbotFilter] = useState("");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [messagesError, setMessagesError] = useState("");
  const [messagesLoading, setMessagesLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const rows = await api.listInbox({
        chatbotId: chatbotFilter || undefined,
        unreadOnly,
      });
      setSessions(rows);
      if (!chatbotFilter && !unreadOnly) {
        onUnreadCountChange?.(rows.filter((s) => s.unread).length);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    api.listChatbots().then(setChatbots).catch(() => {});
  }, []);

  useEffect(() => {
    setSelectedId(null);
    setMessages([]);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatbotFilter, unreadOnly]);

  // Jumping here from a toast notification: clear any filter that might be
  // hiding the target conversation, then open it once it shows up in the
  // freshly loaded list.
  useEffect(() => {
    if (!openSessionId) return;
    setChatbotFilter("");
    setUnreadOnly(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openSessionId]);

  useEffect(() => {
    if (!openSessionId) return;
    const match = sessions.find((s) => s.id === openSessionId);
    if (match) {
      openSession(match);
      onOpenSessionHandled?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openSessionId, sessions]);

  async function openSession(session) {
    setSelectedId(session.id);
    setMessagesError("");
    setMessagesLoading(true);
    try {
      setMessages(await api.listSessionMessages(session.id));
    } catch (err) {
      setMessagesError(err.message);
    } finally {
      setMessagesLoading(false);
    }

    if (session.unread) {
      try {
        await api.markSessionRead(session.id);
        setSessions((prev) => {
          const next = prev.map((s) =>
            s.id === session.id ? { ...s, unread: false } : s
          );
          onUnreadCountChange?.(next.filter((s) => s.unread).length);
          return next;
        });
      } catch {
        // Non-critical -- the transcript still opened either way.
      }
    }
  }

  const unreadCount = sessions.filter((s) => s.unread).length;

  return (
    <section className="inbox-area">
      <aside className="inbox-list-panel">
        <div className="inbox-list-header">
          <h2>Inbox{unreadCount > 0 ? ` (${unreadCount})` : ""}</h2>
        </div>
        <div className="inbox-filters">
          <select
            value={chatbotFilter}
            onChange={(e) => setChatbotFilter(e.target.value)}
          >
            <option value="">All chatbots</option>
            {chatbots.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <label className="inbox-unread-toggle">
            <input
              type="checkbox"
              checked={unreadOnly}
              onChange={(e) => setUnreadOnly(e.target.checked)}
            />
            Unread only
          </label>
        </div>

        {error && <p className="error-text">{error}</p>}

        {loading ? (
          <p className="empty-text">Loading...</p>
        ) : sessions.length === 0 ? (
          <p className="empty-text">
            No conversations yet. Share a chatbot's link to start seeing visitor
            chats here.
          </p>
        ) : (
          <ul className="inbox-list">
            {sessions.map((s) => (
              <li
                key={s.id}
                className={`inbox-item${s.id === selectedId ? " active" : ""}${
                  s.unread ? " unread" : ""
                }`}
                onClick={() => openSession(s)}
              >
                <div className="inbox-item-top">
                  <span className="inbox-item-chatbot">
                    {s.chatbots?.name || "Chatbot"}
                  </span>
                  <span className="inbox-item-time">
                    {timeAgo(s.last_message_at || s.created_at)}
                  </span>
                </div>
                <div className="inbox-item-preview">
                  {s.unread && <span className="inbox-unread-dot" />}
                  {s.last_message_preview || s.title || "New conversation"}
                </div>
              </li>
            ))}
          </ul>
        )}
      </aside>

      <div className="inbox-transcript">
        {!selectedId ? (
          <div className="empty-state-main">
            <p>Select a conversation to read it.</p>
          </div>
        ) : (
          <div className="chat-messages">
            {messagesError && <p className="error-text">{messagesError}</p>}
            {messagesLoading && <p className="empty-text">Loading...</p>}
            {messages.map((m, i) => (
              <div key={i} className={`chat-bubble chat-bubble-${m.role}`}>
                <div className="chat-markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                    {m.content}
                  </ReactMarkdown>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
