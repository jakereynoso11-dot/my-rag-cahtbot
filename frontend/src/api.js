const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const POWABASE_URL = import.meta.env.VITE_POWABASE_URL;
const POWABASE_ANON_KEY = import.meta.env.VITE_POWABASE_ANON_KEY;

const SESSION_KEY = "rag_chatbot_session";

export function loadSession() {
  const raw = localStorage.getItem(SESSION_KEY);
  return raw ? JSON.parse(raw) : null;
}

function saveSession(session) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY);
}

async function authRequest(path, body) {
  const resp = await fetch(`${POWABASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", apikey: POWABASE_ANON_KEY },
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(data.error_description || data.msg || data.message || "Request failed");
  }
  return data;
}

export async function signup(email, password) {
  const data = await authRequest("/auth/v1/signup", { email, password });
  if (data.access_token) saveSession(data);
  return data;
}

export async function signin(email, password) {
  const data = await authRequest("/auth/v1/token?grant_type=password", { email, password });
  saveSession(data);
  return data;
}

async function refreshSession() {
  const session = loadSession();
  if (!session?.refresh_token) throw new Error("No refresh token");
  try {
    const data = await authRequest("/auth/v1/token?grant_type=refresh_token", {
      refresh_token: session.refresh_token,
    });
    saveSession(data);
    return data;
  } catch (err) {
    clearSession();
    throw err;
  }
}

export function logout() {
  clearSession();
}

export async function apiFetch(path, options = {}, allowRetry = true) {
  const session = loadSession();
  const headers = { ...(options.headers || {}) };
  if (session?.access_token) {
    headers.Authorization = `Bearer ${session.access_token}`;
  }

  const resp = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (resp.status === 401 && allowRetry && session?.refresh_token) {
    await refreshSession();
    return apiFetch(path, options, false);
  }

  return resp;
}

export async function listChatbots() {
  const resp = await apiFetch("/chatbots");
  if (!resp.ok) throw new Error("Could not load agents");
  return resp.json();
}

export async function createChatbot(name, systemPrompt) {
  const resp = await apiFetch("/chatbots", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, system_prompt: systemPrompt || null }),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || "Could not create agent");
  return data;
}

export async function renameChatbot(id, name) {
  const resp = await apiFetch(`/chatbots/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || "Could not rename agent");
  return data;
}

export async function deleteChatbot(id) {
  const resp = await apiFetch(`/chatbots/${id}`, { method: "DELETE" });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || "Could not delete agent");
  }
}

export async function deleteChatSession(id) {
  const resp = await apiFetch(`/chat/sessions/${id}`, { method: "DELETE" });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || "Could not delete conversation");
  }
}
