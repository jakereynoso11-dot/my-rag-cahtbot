import { useAuth } from "../AuthContext";
import DocumentsPanel from "./DocumentsPanel";
import ChatWindow from "./ChatWindow";

export default function Dashboard() {
  const { session, logout } = useAuth();

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>Knowledge Assistant</h1>
        <div className="header-right">
          <span className="user-email">{session?.user?.email}</span>
          <button onClick={logout}>Log out</button>
        </div>
      </header>
      <div className="dashboard-body">
        <DocumentsPanel />
        <ChatWindow />
      </div>
    </div>
  );
}
