import { useState } from "react";
import { useAuth } from "../AuthContext";
import ChatbotsList from "./ChatbotsList";
import DocumentsPanel from "./DocumentsPanel";
import ChatWindow from "./ChatWindow";
import OnboardingGuide from "./OnboardingGuide";

export default function Dashboard() {
  const { session, logout } = useAuth();
  const [selectedChatbot, setSelectedChatbot] = useState(null);
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
        {selectedChatbot ? (
          <div className="chatbot-workspace">
            <div className="workspace-header">
              <button className="link-button" onClick={() => setSelectedChatbot(null)}>
                ← My Chatbots
              </button>
              <div className="workspace-title">
                <h2>{selectedChatbot.name}</h2>
                {selectedChatbot.system_prompt && (
                  <p className="workspace-purpose">{selectedChatbot.system_prompt}</p>
                )}
              </div>
            </div>
            <div className="workspace-body">
              <DocumentsPanel chatbotId={selectedChatbot.id} />
              <ChatWindow chatbotId={selectedChatbot.id} />
            </div>
          </div>
        ) : (
          <ChatbotsList onOpen={setSelectedChatbot} />
        )}
      </div>
    </div>
  );
}
