import { useEffect, useState } from "react";

const STORAGE_KEY = "rag_chatbot_onboarding_complete";

const STEPS = [
  {
    title: "Welcome to Knowledge Assistant",
    body: "This quick tour shows you how to set up and chat with your own AI agents. It only takes a minute.",
  },
  {
    title: "1. Create an agent",
    body: 'In the left sidebar, click "+ New" to create an agent. Give it a name and, optionally, instructions for how it should behave — e.g. "You\'re a tax assistant, only answer from the uploaded documents."',
  },
  {
    title: "2. Upload documents",
    body: "Select an agent, then use the Documents panel to upload PDFs. Each agent only sees the documents you give it — uploads never mix between agents.",
  },
  {
    title: "3. Chat",
    body: "Ask your agent questions in the chat panel. It answers using only the documents you uploaded to it, and keeps a history of your conversations so you can pick up where you left off.",
  },
  {
    title: "You're all set",
    body: "Create as many agents as you like — one per project, topic, or use case. You can rename or delete an agent anytime from the sidebar. Click \"? Help\" in the header to see this tour again.",
  },
];

export function hasSeenOnboarding() {
  return localStorage.getItem(STORAGE_KEY) === "true";
}

export default function OnboardingGuide({ forceOpen, onClose }) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (forceOpen || !hasSeenOnboarding()) {
      setStep(0);
      setOpen(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [forceOpen]);

  function finish() {
    localStorage.setItem(STORAGE_KEY, "true");
    setOpen(false);
    onClose?.();
  }

  if (!open) return null;

  const isLast = step === STEPS.length - 1;
  const current = STEPS[step];

  return (
    <div className="onboarding-overlay">
      <div className="onboarding-card">
        <p className="onboarding-progress">
          {step + 1} / {STEPS.length}
        </p>
        <h2>{current.title}</h2>
        <p>{current.body}</p>
        <div className="onboarding-actions">
          <button type="button" className="link-button" onClick={finish}>
            Skip
          </button>
          <div className="onboarding-nav">
            {step > 0 && (
              <button type="button" onClick={() => setStep((s) => s - 1)}>
                Back
              </button>
            )}
            {isLast ? (
              <button type="button" onClick={finish}>
                Done
              </button>
            ) : (
              <button type="button" onClick={() => setStep((s) => s + 1)}>
                Next
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
