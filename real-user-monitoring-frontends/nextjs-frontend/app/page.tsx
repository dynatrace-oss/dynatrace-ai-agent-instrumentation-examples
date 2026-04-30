"use client";

import { useEffect, useRef, useState } from "react";

// ── Dynatrace RUM global (injected by the <Script> tag in layout.tsx) ──────
declare global {
  interface Window {
    dtrum?: {
      sendSessionProperties: (
        p: Record<string, string | number | boolean>
      ) => void;
      addActionProperties: (
        p: Record<string, string | number | boolean>
      ) => void;
    };
  }
}

// ── Static data ─────────────────────────────────────────────────────────────
const QUESTIONS: Record<string, string[]> = {
  Jazz: [
    "Who invented bebop and why did it split the jazz world?",
    "How did Miles Davis reinvent jazz three separate times?",
    "What made John Coltrane's A Love Supreme a spiritual experience?",
    "Why is New Orleans considered the birthplace of jazz?",
    "How did Duke Ellington turn a big band into an orchestra?",
    "What is the difference between cool jazz and hard bop?",
  ],
  "Classic Rock": [
    "How did Led Zeppelin change the sound of rock forever?",
    "Why did the Beatles break up and what was the lasting fallout?",
    "What makes the Rolling Stones still relevant after 60 years?",
    "How did Jimi Hendrix redefine what a guitar could do?",
    "What was the cultural impact of Woodstock 1969?",
    "Why is Dark Side of the Moon considered a concept album masterpiece?",
  ],
  Classical: [
    "How did Beethoven keep composing after going deaf?",
    "What makes Bach's fugues mathematically beautiful?",
    "Why did Mozart die in poverty despite his genius?",
    "How did Stravinsky's Rite of Spring cause a riot at its premiere?",
    "What is the difference between a symphony and a concerto?",
    "How did Chopin capture Polish identity in piano music?",
  ],
};

// ── Types ────────────────────────────────────────────────────────────────────
interface Message {
  id: string;
  question: string;
  answer?: string;
  provider?: string;
  model?: string;
  conversationId?: string;
  error?: string;
  loading: boolean;
  feedback?: "thumbs_up" | "thumbs_down";
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function getConversationId(): string {
  const stored = sessionStorage.getItem("conversationId");
  if (stored) return stored;
  const id = crypto.randomUUID();
  sessionStorage.setItem("conversationId", id);
  return id;
}

async function sendFeedback(
  rating: "thumbs_up" | "thumbs_down",
  question: string,
  conversationId: string,
  provider: string,
  model: string
) {
  try {
    await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rating, question, conversation_id: conversationId, provider, model }),
    });
  } catch (_) {}
}

function copyToClipboard(text: string, onDone: () => void) {
  navigator.clipboard.writeText(text).then(onDone).catch(() => {});
}

// ── Component ────────────────────────────────────────────────────────────────
export default function Page() {
  const [conversationId, setConversationId] = useState("");
  const [rumActive, setRumActive] = useState(false);
  const [category, setCategory] = useState("Jazz");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [convCopied, setConvCopied] = useState(false);
  const chatRef = useRef<HTMLDivElement>(null);

  // Initialise conversation ID and RUM session properties on mount
  useEffect(() => {
    const id = getConversationId();
    setConversationId(id);

    const rumReady = typeof window.dtrum !== "undefined";
    setRumActive(rumReady);

    if (rumReady) {
      window.dtrum!.sendSessionProperties({ conversationId: id });
    }
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function ask(question: string) {
    if (!question.trim() || busy) return;
    setBusy(true);
    setInput("");

    // Stamp RUM user-action with conversation context before fetch fires
    if (typeof window.dtrum !== "undefined") {
      window.dtrum!.addActionProperties({
        conversationId,
        question: question.substring(0, 100),
      });
    }

    const msgId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      { id: msgId, question, loading: true },
    ]);

    try {
      // DT RUM JS auto-injects W3C traceparent into this fetch call,
      // linking this browser user-action span to the backend OTel span.
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, conversation_id: conversationId }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Request failed" }));
        throw new Error(err.detail ?? "Request failed");
      }

      const data = await res.json();

      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId
            ? {
                ...m,
                loading: false,
                answer: data.answer,
                provider: data.provider,
                model: data.model,
                conversationId: data.conversation_id,
              }
            : m
        )
      );
    } catch (err: unknown) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId
            ? { ...m, loading: false, error: (err as Error).message }
            : m
        )
      );
    }

    setBusy(false);
  }

  function handleFeedback(
    msgId: string,
    rating: "thumbs_up" | "thumbs_down",
    question: string,
    conversationId: string,
    provider: string,
    model: string
  ) {
    setMessages((prev) =>
      prev.map((m) => (m.id === msgId ? { ...m, feedback: rating } : m))
    );
    sendFeedback(rating, question, conversationId, provider, model);
  }

  function copyConvDql() {
    const dql = `fetch spans\n| filter conversation.id == "${conversationId}"`;
    copyToClipboard(dql, () => {
      setConvCopied(true);
      setTimeout(() => setConvCopied(false), 1500);
    });
  }

  return (
    <div className="shell">
      {/* ── Conversation bar ── */}
      <div className="conv-bar">
        <span>Conversation</span>
        <span className="conv-id">{conversationId.substring(0, 8)}…</span>
        <button className="btn" onClick={copyConvDql}>
          {convCopied ? "Copied!" : "Copy for DQL"}
        </button>
        <span className="rum-dot" style={{ background: rumActive ? "#4caf50" : undefined }} />
        <span className="rum-label">{rumActive ? "RUM active" : "RUM not detected"}</span>
      </div>

      {/* ── Header ── */}
      <div className="header">
        <h1>Music History Explorer</h1>
        <p>Ask anything about jazz, classic rock, or classical music.</p>
      </div>

      {/* ── Category tabs ── */}
      <div className="tabs">
        {Object.keys(QUESTIONS).map((cat) => (
          <button
            key={cat}
            className={`tab${category === cat ? " active" : ""}`}
            onClick={() => setCategory(cat)}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* ── Question chips ── */}
      <div className="chips">
        {QUESTIONS[category].map((q) => (
          <button key={q} className="chip" onClick={() => ask(q)}>
            {q}
          </button>
        ))}
      </div>

      {/* ── Chat area ── */}
      <div className="chat-area" ref={chatRef}>
        {messages.map((msg) => (
          <div key={msg.id} className="message">
            <div className="question-bubble">{msg.question}</div>

            {msg.loading && (
              <div className="loading-block">
                <div className="dots">
                  <span /><span /><span />
                </div>
                Thinking…
              </div>
            )}

            {msg.error && (
              <div className="error-bubble">Error: {msg.error}</div>
            )}

            {msg.answer && (
              <AnswerBlock
                msg={msg}
                onFeedback={(rating) =>
                  handleFeedback(
                    msg.id,
                    rating,
                    msg.question,
                    msg.conversationId!,
                    msg.provider!,
                    msg.model!
                  )
                }
              />
            )}
          </div>
        ))}
      </div>

      {/* ── Input ── */}
      <div className="input-area">
        <div className="input-row">
          <input
            type="text"
            placeholder="Ask about music history…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask(input)}
            disabled={busy}
          />
          <button className="send-btn" onClick={() => ask(input)} disabled={busy || !input.trim()}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

// ── AnswerBlock ───────────────────────────────────────────────────────────────
function AnswerBlock({
  msg,
  onFeedback,
}: {
  msg: Message;
  onFeedback: (r: "thumbs_up" | "thumbs_down") => void;
}) {
  const [feedbackCopied, setFeedbackCopied] = useState(false);
  const isAzure = msg.provider?.toLowerCase().includes("azure");

  function copyFeedbackDql() {
    const dql = `fetch spans\n| filter span.name == "music_agent.feedback"\n| filter conversation.id == "${msg.conversationId}"\n| fields timestamp, feedback.rating, feedback.question, gen_ai.provider.name, gen_ai.request.model`;
    copyToClipboard(dql, () => {
      setFeedbackCopied(true);
      setTimeout(() => setFeedbackCopied(false), 1500);
    });
  }

  return (
    <div className="answer-block">
      <div className="meta-row">
        <div className={`provider-badge ${isAzure ? "azure" : "bedrock"}`}>
          <span className="dot" />
          {msg.provider} · {msg.model?.split("/").pop()}
        </div>
        <div className="conv-badge" title={`Full ID: ${msg.conversationId}`}>
          conv: {msg.conversationId?.substring(0, 8)}…
        </div>
      </div>

      <div className="answer-bubble">{msg.answer}</div>

      <div className="feedback-row">
        <button
          className={`feedback-btn${msg.feedback === "thumbs_up" ? " active-up" : ""}`}
          disabled={!!msg.feedback}
          onClick={() => onFeedback("thumbs_up")}
          title="Good answer"
        >
          👍
        </button>
        <button
          className={`feedback-btn${msg.feedback === "thumbs_down" ? " active-down" : ""}`}
          disabled={!!msg.feedback}
          onClick={() => onFeedback("thumbs_down")}
          title="Bad answer"
        >
          👎
        </button>
        <button className="feedback-btn" onClick={copyFeedbackDql} title="Copy feedback DQL query">
          {feedbackCopied ? "Copied!" : "Copy DQL"}
        </button>
      </div>
    </div>
  );
}
