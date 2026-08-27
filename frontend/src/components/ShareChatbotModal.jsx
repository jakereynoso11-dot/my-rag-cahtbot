import { useState } from "react";

export default function ShareChatbotModal({ chatbot, onClose }) {
  const [copied, setCopied] = useState("");

  const shareUrl = `${window.location.origin}/share/${chatbot.share_token}`;
  const embedSnippet = `<script src="${window.location.origin}/widget.js" data-chatbot="${chatbot.share_token}"></script>`;
  const demoUrl = `${window.location.origin}/demo.html?chatbot=${chatbot.share_token}`;

  async function copy(text, which) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      window.prompt("Copy this:", text);
      return;
    }
    setCopied(which);
    setTimeout(() => setCopied((c) => (c === which ? "" : c)), 1500);
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h2>Share &ldquo;{chatbot.name}&rdquo;</h2>
        <p className="share-modal-hint">
          Anyone with the link below can chat with this agent directly -- no login
          required, and each visitor gets their own private conversation.
        </p>

        <div className="share-section">
          <label>Direct link</label>
          <div className="share-copy-row">
            <input
              type="text"
              readOnly
              value={shareUrl}
              onFocus={(e) => e.target.select()}
            />
            <button type="button" onClick={() => copy(shareUrl, "link")}>
              {copied === "link" ? "Copied!" : "Copy"}
            </button>
          </div>
        </div>

        <div className="share-section">
          <label>Embed on a website</label>
          <p className="share-modal-hint">
            Paste this into any website's HTML to add a floating chat bubble to
            that page.
          </p>
          <div className="share-copy-row">
            <code className="share-code-box">{embedSnippet}</code>
            <button type="button" onClick={() => copy(embedSnippet, "embed")}>
              {copied === "embed" ? "Copied!" : "Copy"}
            </button>
          </div>
        </div>

        <a
          className="link-button share-preview-link"
          href={demoUrl}
          target="_blank"
          rel="noreferrer"
        >
          ↗ Preview the widget on a sample page
        </a>

        <div className="modal-actions">
          <button type="button" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
