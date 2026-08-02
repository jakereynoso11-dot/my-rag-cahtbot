import { useState } from "react";
import { useAuth } from "../AuthContext";
import AgentsPanel from "./AgentsPanel";
import DocumentsPanel from "./DocumentsPanel";
import ChatWindow from "./ChatWindow";
import OnboardingGuide from "./OnboardingGuide";

export default function Dashboard() {
  const { session, logout } = useAuth();
  const [selectedChatbotId, setSelectedChatbotId] = useState(null);
  const [showHelp, setShowHelp] = useState(false);

  return (
    <div className="dashboard">
      <OnboardingGuide forceOpen={showHelp} onClose={() => setShowHelp(false)} />
      <header className="dashboard-header">
        <h1>Knowledge Assistant</h1>
        <div className="header-right">
          <button className="link-button" onClick={() => setShowHelp(true)}>
            ? Help
          </button>
          <span className="user-email">{session?.user?.email}</span>
          <button onClick={logout}>Log out</button>
        </div>
      </header>
      <div className="dashboard-body">
        <AgentsPanel selectedId={selectedChatbotId} onSelect={setSelectedChatbotId} />
        {selectedChatbotId ? (
          <>
            <DocumentsPanel chatbotId={selectedChatbotId} />
            <ChatWindow chatbotId={selectedChatbotId} />
          </>
        ) : (
          <div className="empty-state-main">
            <p>Create an agent on the left to get started.</p>
          </div>
        )}
      </div>
    </div>
  );
}
