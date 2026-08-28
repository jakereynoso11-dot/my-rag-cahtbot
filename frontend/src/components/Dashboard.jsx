import { useEffect, useRef, useState } from "react";
import { useAuth } from "../AuthContext";
import * as api from "../api";
import AgentsPanel from "./AgentsPanel";
import DocumentsPanel from "./DocumentsPanel";
import SpecialistsPanel from "./SpecialistsPanel";
import ChatWindow from "./ChatWindow";
import InboxPanel from "./InboxPanel";
import OnboardingGuide from "./OnboardingGuide";
import { applyTheme, getStoredTheme } from "../theme";

const POLL_INTERVAL_MS = 15000;
const TOAST_LIFETIME_MS = 6000;

export default function Dashboard() {
  const { session, logout } = useAuth();
  const [selectedChatbotId, setSelectedChatbotId] = useState(null);
  const [showHelp, setShowHelp] = useState(false);
  const [chatbotCount, setChatbotCount] = useState(null);
  const [theme, setTheme] = useState(getStoredTheme);
  const [view, setView] = useState("chatbots");
  const [unreadCount, setUnreadCount] = useState(0);
  const [justNotified, setJustNotified] = useState(false);
  const [toasts, setToasts] = useState([]);
  const [openSessionId, setOpenSessionId] = useState(null);
  const seenUnreadIds = useRef(null);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    setTheme(next);
  }

  function dismissToast(id) {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }

  function openToastConversation(toast) {
    dismissToast(toast.id);
    setOpenSessionId(toast.id);
    setView("inbox");
  }

  useEffect(() => {
    let cancelled = false;
    async function pollUnread() {
      try {
        const rows = await api.listInbox({ unreadOnly: true });
        if (cancelled) return;
        setUnreadCount(rows.length);

        // Only ring the bell for conversations that showed up since the
        // last poll -- the very first poll just establishes the baseline,
        // so a user doesn't get flooded with toasts for old unread chats
        // on page load.
        if (seenUnreadIds.current) {
          const freshRows = rows.filter((r) => !seenUnreadIds.current.has(r.id));
          if (freshRows.length > 0) {
            setJustNotified(true);
            setTimeout(() => setJustNotified(false), 4000);
            setToasts((prev) => [
              ...prev,
              ...freshRows.map((r) => ({
                id: r.id,
                chatbotName: r.chatbots?.name || "Chatbot",
                preview: r.last_message_preview || "New conversation",
              })),
            ]);
            freshRows.forEach((r) => {
              setTimeout(() => dismissToast(r.id), TOAST_LIFETIME_MS);
            });
          }
        }
        seenUnreadIds.current = new Set(rows.map((r) => r.id));
      } catch {
        // The badge/toasts are a convenience; a failed poll just leaves them stale.
      }
    }
    pollUnread();
    const interval = setInterval(pollUnread, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="dashboard">
      <OnboardingGuide
        forceOpen={showHelp}
        isNewUser={chatbotCount === 0}
        onClose={() => setShowHelp(false)}
      />
      <header className="dashboard-header">
        <h1>Knowledge Assistant</h1>
        <div className="header-right">
          <button
            className={view === "inbox" ? "inbox-nav-button active" : "inbox-nav-button"}
            onClick={() => setView(view === "inbox" ? "chatbots" : "inbox")}
            title="See what visitors are asking your chatbots"
          >
            📥 Inbox{unreadCount > 0 ? ` (${unreadCount})` : ""}
            {unreadCount > 0 && (
              <span className={justNotified ? "notification-dot pulse" : "notification-dot"} />
            )}
          </button>
          <button
            className="icon-button"
            onClick={toggleTheme}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? "☀️" : "🌙"}
          </button>
          <button className="link-button" onClick={() => setShowHelp(true)}>
            ? Help
          </button>
          <span className="user-email">{session?.user?.email}</span>
          <button onClick={logout}>Log out</button>
        </div>
      </header>
      {toasts.length > 0 && (
        <div className="toast-stack">
          {toasts.map((t) => (
            <div key={t.id} className="toast" onClick={() => openToastConversation(t)}>
              <span className="toast-icon">💬</span>
              <div className="toast-body">
                <div className="toast-title">New message &middot; {t.chatbotName}</div>
                <div className="toast-preview">{t.preview}</div>
              </div>
              <button
                className="toast-dismiss"
                onClick={(e) => {
                  e.stopPropagation();
                  dismissToast(t.id);
                }}
                title="Dismiss"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
      <div className="dashboard-body">
        {view === "inbox" ? (
          <InboxPanel
            onUnreadCountChange={setUnreadCount}
            openSessionId={openSessionId}
            onOpenSessionHandled={() => setOpenSessionId(null)}
          />
        ) : (
          <>
            <AgentsPanel
              selectedId={selectedChatbotId}
              onSelect={setSelectedChatbotId}
              onAgentsLoaded={setChatbotCount}
            />
            {selectedChatbotId ? (
              <>
                <div className="side-panels">
                  <DocumentsPanel chatbotId={selectedChatbotId} />
                  <SpecialistsPanel chatbotId={selectedChatbotId} />
                </div>
                <ChatWindow chatbotId={selectedChatbotId} />
              </>
            ) : (
              <div className="empty-state-main">
                <p>Create a chatbot on the left to get started.</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
