import { AuthProvider, useAuth } from "./AuthContext";
import Auth from "./components/Auth";
import Dashboard from "./components/Dashboard";
import PublicChat from "./components/PublicChat";
import "./styles.css";

function AppInner() {
  const { session } = useAuth();
  return session ? <Dashboard /> : <Auth />;
}

// A public share link (/chat/<token>) is a standalone page for anonymous
// visitors -- it never touches AuthProvider/Powabase login at all.
const publicChatMatch = window.location.pathname.match(/^\/chat\/([^/]+)\/?$/);

export default function App() {
  if (publicChatMatch) {
    return <PublicChat shareToken={publicChatMatch[1]} />;
  }

  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  );
}
