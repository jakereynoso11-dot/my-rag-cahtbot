import { useState } from "react";
import { useAuth } from "../AuthContext";
import AgentsPanel from "./AgentsPanel";
import DocumentsPanel from "./DocumentsPanel";
import SpecialistsPanel from "./SpecialistsPanel";
import ChatWindow from "./ChatWindow";
import OnboardingGuide from "./OnboardingGuide";
import { applyTheme, getStoredTheme } from "../theme";

export default function Dashboard() {
  const { session, logout } = useAuth();
  const [selectedChatbotId, setSelectedChatbotId] = useState(null);
  const [showHelp, setShowHelp] = useState(false);
  const [chatbotCount, setChatbotCount] = useState(null);
  const [theme, setTheme] = useState(getStoredTheme);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    setTheme(next);
  }

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
      <div className="dashboard-body">
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
      </div>
    </div>
  );
}
