import { useEffect, useState } from "react";

const STORAGE_KEY = "rag_chatbot_onboarding_complete";

const STEPS = [
  {
    title: "Welcome to Knowledge Assistant",
    body: "This quick tour shows you how to set up and chat with your own AI agents. It only takes a minute.",
  },
  {
    title: "1. Create an agent",
    body: 'Click "+ New" here to create an agent. Give it a name and, optionally, instructions for how it should behave — e.g. "You\'re a tax assistant, only answer from the uploaded documents."',
    target: "agents-panel",
    placement: "right",
  },
  {
    title: "2. Upload documents",
    body: "Select an agent, then use this panel to upload PDFs. Each agent only sees the documents you give it — uploads never mix between agents.",
    target: "documents-panel",
    placement: "right",
  },
  {
    title: "3. Chat",
    body: "Ask your agent questions here. It answers using only the documents you uploaded to it, and keeps a history of your conversations so you can pick up where you left off.",
    target: "chat-input-row",
    placement: "top",
  },
  {
    title: "4. Add specialists (optional)",
    body: 'Use this panel to spin up a topic expert — e.g. a "Billing Agent" specializing in "billing and invoice questions." No documents needed to create one: it works immediately, and your chatbot automatically hands off matching questions to it.',
    target: "specialists-panel",
    placement: "right",
  },
  {
    title: "You're all set",
    body: "Create as many agents as you like — one per project, topic, or use case. You can rename, edit, or delete an agent anytime from the sidebar. Click \"? Help\" in the header to see this tour again.",
  },
];

export function hasSeenOnboarding() {
  return localStorage.getItem(STORAGE_KEY) === "true";
}

function useTargetRect(selector, open) {
  const [rect, setRect] = useState(null);

  useEffect(() => {
    if (!open || !selector) {
      setRect(null);
      return;
    }

    function measure() {
      const el = document.querySelector(`[data-tour="${selector}"]`);
      setRect(el ? el.getBoundingClientRect() : null);
    }

    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    const interval = setInterval(measure, 300);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
      clearInterval(interval);
    };
  }, [selector, open]);

  return rect;
}

function bubbleStyle(rect, placement) {
  const gap = 16;
  const bubbleWidth = 320;
  if (placement === "top") {
    return {
      left: Math.min(
        Math.max(rect.left + rect.width / 2 - bubbleWidth / 2, 16),
        window.innerWidth - bubbleWidth - 16
      ),
      top: rect.top - gap,
      transform: "translateY(-100%)",
    };
  }
  // default: right
  return {
    left: Math.min(rect.right + gap, window.innerWidth - bubbleWidth - 16),
    top: Math.min(Math.max(rect.top, 16), window.innerHeight - 220),
  };
}

export default function OnboardingGuide({ forceOpen, onClose }) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  const current = STEPS[step];
  const rect = useTargetRect(current?.target, open);

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
  const spotlighted = Boolean(current.target && rect);

  const nav = (
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
  );

  if (!spotlighted) {
    return (
      <div className="onboarding-overlay">
        <div className="onboarding-card">
          <p className="onboarding-progress">
            {step + 1} / {STEPS.length}
          </p>
          <h2>{current.title}</h2>
          <p>{current.body}</p>
          {nav}
        </div>
      </div>
    );
  }

  const padding = 8;
  const spotlightRect = {
    left: rect.left - padding,
    top: rect.top - padding,
    width: rect.width + padding * 2,
    height: rect.height + padding * 2,
  };

  return (
    <div className="tour-scrim">
      <div
        className="tour-spotlight"
        style={{
          left: spotlightRect.left,
          top: spotlightRect.top,
          width: spotlightRect.width,
          height: spotlightRect.height,
        }}
      />
      <div
        className={`tour-bubble tour-bubble-${current.placement || "right"}`}
        style={bubbleStyle(rect, current.placement)}
      >
        <p className="onboarding-progress">
          {step + 1} / {STEPS.length}
        </p>
        <h2>{current.title}</h2>
        <p>{current.body}</p>
        {nav}
      </div>
    </div>
  );
}
