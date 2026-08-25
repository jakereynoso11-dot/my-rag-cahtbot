(function () {
  "use strict";

  var thisScript = document.currentScript;
  var shareToken = thisScript && thisScript.getAttribute("data-chatbot");
  if (!shareToken) {
    console.error(
      "[chat widget] missing data-chatbot=\"...\" attribute on the widget <script> tag -- nothing to embed."
    );
    return;
  }

  // Derive the widget's own origin from wherever this script itself was
  // loaded from, so the exact same snippet works no matter which chatbot
  // platform deployment is serving it -- no domain hardcoded here.
  var origin = new URL(thisScript.src).origin;

  var BUBBLE_SIZE = 56;
  var PANEL_WIDTH = 380;
  var PANEL_HEIGHT = 600;
  var GAP = 20;
  var Z_INDEX = 2147483000; // stay above virtually anything a host page has

  var isOpen = false;

  var bubble = document.createElement("button");
  bubble.type = "button";
  bubble.setAttribute("aria-label", "Open chat");
  bubble.textContent = "💬"; // 💬
  Object.assign(bubble.style, {
    position: "fixed",
    bottom: GAP + "px",
    right: GAP + "px",
    width: BUBBLE_SIZE + "px",
    height: BUBBLE_SIZE + "px",
    borderRadius: "50%",
    border: "none",
    background: "#4f7cff",
    color: "#fff",
    fontSize: "24px",
    lineHeight: BUBBLE_SIZE + "px",
    textAlign: "center",
    padding: "0",
    cursor: "pointer",
    boxShadow: "0 4px 16px rgba(0,0,0,0.25)",
    zIndex: Z_INDEX,
  });

  var panel = document.createElement("iframe");
  panel.title = "Chat";
  panel.src = origin + "/share/" + encodeURIComponent(shareToken);
  Object.assign(panel.style, {
    position: "fixed",
    border: "none",
    borderRadius: "12px",
    boxShadow: "0 8px 32px rgba(0,0,0,0.3)",
    zIndex: Z_INDEX,
    display: "none",
    colorScheme: "light dark",
  });

  function applyLayout() {
    var narrow = window.innerWidth < 480;
    if (narrow) {
      Object.assign(panel.style, {
        width: "100vw",
        height: "100vh",
        maxHeight: "100vh",
        bottom: "0",
        right: "0",
        borderRadius: "0",
      });
    } else {
      Object.assign(panel.style, {
        width: PANEL_WIDTH + "px",
        height: PANEL_HEIGHT + "px",
        maxHeight: "70vh",
        bottom: BUBBLE_SIZE + GAP * 2 + "px",
        right: GAP + "px",
        borderRadius: "12px",
      });
    }
  }

  function toggle() {
    isOpen = !isOpen;
    panel.style.display = isOpen ? "block" : "none";
    bubble.textContent = isOpen ? "✕" : "💬"; // ✕ or 💬
    bubble.setAttribute("aria-label", isOpen ? "Close chat" : "Open chat");
  }

  bubble.addEventListener("click", toggle);
  window.addEventListener("resize", applyLayout);

  function mount() {
    applyLayout();
    document.body.appendChild(panel);
    document.body.appendChild(bubble);
  }

  if (document.body) {
    mount();
  } else {
    document.addEventListener("DOMContentLoaded", mount);
  }
})();
