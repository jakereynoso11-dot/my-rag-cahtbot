import { AuthProvider, useAuth } from "./AuthContext";
import Auth from "./components/Auth";
import Dashboard from "./components/Dashboard";
import PublicChat from "./components/PublicChat";
import "./styles.css";

function AppInner() {
  const { session } = useAuth();
  return session ? <Dashboard /> : <Auth />;
}

// A public share link (/share/<token>) is a standalone page for anonymous
// visitors -- it never touches AuthProvider/Powabase login at all. This is
// deliberately NOT under /chat/* -- the backend's own /chat* API routes are
// reverse-proxied at that prefix (see deploy/Caddyfile), so a frontend page
// there would never actually be served.
const publicChatMatch = window.location.pathname.match(/^\/share\/([^/]+)\/?$/);

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
