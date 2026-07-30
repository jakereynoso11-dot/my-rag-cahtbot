import { createContext, useCallback, useContext, useState } from "react";
import * as api from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(() => api.loadSession());

  const login = useCallback(async (email, password) => {
    const s = await api.signin(email, password);
    setSession(s);
    return s;
  }, []);

  const signup = useCallback(async (email, password) => {
    const s = await api.signup(email, password);
    if (s.access_token) setSession(s);
    return s;
  }, []);

  const logout = useCallback(() => {
    api.logout();
    setSession(null);
  }, []);

  return (
    <AuthContext.Provider value={{ session, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
