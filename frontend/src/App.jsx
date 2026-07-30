import { AuthProvider, useAuth } from "./AuthContext";
import Auth from "./components/Auth";
import Dashboard from "./components/Dashboard";
import "./styles.css";

function AppInner() {
  const { session } = useAuth();
  return session ? <Dashboard /> : <Auth />;
}

export default function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  );
}
