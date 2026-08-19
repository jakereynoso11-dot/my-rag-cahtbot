const STORAGE_KEY = "rag_chatbot_theme";

export function getStoredTheme() {
  return localStorage.getItem(STORAGE_KEY) || "dark";
}

export function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem(STORAGE_KEY, theme);
}
