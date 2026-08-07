import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { ReferencesPanel } from "./components/ReferencesPanel";
import type { Health, Message, Session } from "./types";

/** Render answer text, turning [n] markers into clickable citation chips. */
function AnswerText({
  text,
  onCite,
}: {
  text: string;
  onCite: (n: number) => void;
}) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <>
      {parts.map((p, i) => {
        const m = p.match(/^\[(\d+)\]$/);
        if (m) {
          const n = Number(m[1]);
          return (
            <span key={i} className="cite" onClick={() => onCite(n)}>
              {n}
            </span>
          );
        }
        return <span key={i}>{p}</span>;
      })}
    </>
  );
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [presets, setPresets] = useState<string[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedMsg, setSelectedMsg] = useState<Message | null>(null);
  const [tab, setTab] = useState<"refs" | "trace">("refs");
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [armedDeleteId, setArmedDeleteId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setError("Backend not reachable"));
    api.presets().then((p) => setPresets(p.questions)).catch(() => {});
    refreshSessions();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function refreshSessions() {
    try {
      const s = await api.listSessions();
      setSessions(s);
      if (s.length && !activeSession) selectSession(s[0].id);
    } catch {
      /* backend not up yet */
    }
  }

  async function selectSession(id: string) {
    setActiveSession(id);
    const msgs = await api.getMessages(id);
    setMessages(msgs);
    const lastAssistant = [...msgs].reverse().find((m) => m.role === "assistant");
    setSelectedMsg(lastAssistant ?? null);
    setHighlighted(null);
  }

  async function commitRename(id: string) {
    const title = editTitle.trim();
    setEditingId(null);
    if (!title) return;
    await api.renameSession(id, title);
    setSessions((prev) => prev.map((s) => (s.id === id ? { ...s, title } : s)));
  }

  async function removeSession(id: string) {
    setArmedDeleteId(null);
    await api.deleteSession(id);
    const remaining = sessions.filter((s) => s.id !== id);
    setSessions(remaining);
    if (activeSession === id) {
      if (remaining.length) {
        selectSession(remaining[0].id);
      } else {
        setActiveSession(null);
        setMessages([]);
        setSelectedMsg(null);
      }
    }
  }

  async function newSession() {
    const s = await api.createSession();
    setSessions((prev) => [s, ...prev]);
    setActiveSession(s.id);
    setMessages([]);
    setSelectedMsg(null);
    setHighlighted(null);
  }

  async function ask(question: string) {
    if (!question.trim() || busy) return;
    setError(null);
    let sid = activeSession;
    if (!sid) {
      const s = await api.createSession();
      setSessions((prev) => [s, ...prev]);
      setActiveSession(s.id);
      sid = s.id;
    }
    setInput("");
    setBusy(true);
    const userMsg: Message = {
      id: `local-${Date.now()}`,
      role: "user",
      content: question,
      covered: null,
      citations: [],
      trace: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    try {
      const res = await api.ask(sid, question);
      const assistantMsg: Message = {
        id: res.message_id,
        role: "assistant",
        content: res.answer,
        covered: res.covered,
        citations: res.citations,
        trace: res.trace,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setSelectedMsg(assistantMsg);
      setTab("refs");
      setHighlighted(null);
      refreshSessions();
    } catch (e: any) {
      setError(e.message ?? "Request failed");
    } finally {
      setBusy(false);
    }
  }

  function onCite(msg: Message, n: number) {
    setSelectedMsg(msg);
    setTab("refs");
    setHighlighted(n);
    setTimeout(() => {
      document.getElementById(`ref-${n}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 50);
  }

  return (
    <>
      <header className="header">
        <span className="logo">
          Salvi <em>· Executive Oracle</em>
        </span>
        <span className="subtitle">Executive House transcripts</span>
        <span className="spacer" />
        {health && (
          <span className="badge">
            <span className="dot" />
            {health.vector_store.points} chunks indexed · {health.answer_model}
          </span>
        )}
        <span className="badge user">
          <span className="dot" />
          admin
        </span>
      </header>

      <div className="layout">
        <nav className="sessions">
          <button className="new-chat" onClick={newSession}>
            + New session
          </button>
          <h3>Sessions</h3>
          <div className="session-list">
            {sessions.map((s) => (
              <div
                key={s.id}
                className={`session-item ${s.id === activeSession ? "active" : ""}`}
                onClick={() => editingId !== s.id && selectSession(s.id)}
                title={s.title}
              >
                {editingId === s.id ? (
                  <input
                    className="rename-input"
                    value={editTitle}
                    autoFocus
                    onChange={(e) => setEditTitle(e.target.value)}
                    onBlur={() => commitRename(s.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") commitRename(s.id);
                      if (e.key === "Escape") setEditingId(null);
                    }}
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  <>
                    <span className="session-title">{s.title}</span>
                    <span className="session-actions">
                      {armedDeleteId === s.id ? (
                        <button
                          className="confirm-delete"
                          title="Click to confirm delete"
                          onClick={(e) => {
                            e.stopPropagation();
                            removeSession(s.id);
                          }}
                          onMouseLeave={() => setArmedDeleteId(null)}
                        >
                          Delete?
                        </button>
                      ) : (
                        <>
                          <button
                            className="icon-btn"
                            title="Rename"
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingId(s.id);
                              setEditTitle(s.title);
                            }}
                          >
                            ✎
                          </button>
                          <button
                            className="icon-btn danger"
                            title="Delete"
                            onClick={(e) => {
                              e.stopPropagation();
                              setArmedDeleteId(s.id);
                            }}
                          >
                            🗑
                          </button>
                        </>
                      )}
                    </span>
                  </>
                )}
              </div>
            ))}
          </div>
        </nav>

        <main className="chat">
          <div className="messages">
            {messages.length === 0 && !busy && (
              <div className="empty-state">
                <h2>Ask the transcripts</h2>
                <p>
                  Grounded answers from the Eventbrite (Julia &amp; Kevin Hartz) and
                  QED Investors / Capital One (Nigel Morris) Executive House
                  interviews — with citations to who said it, when, and where.
                </p>
                <p>If it isn't in the transcripts, the Oracle says so.</p>
              </div>
            )}
            {messages.map((m) => (
              <div key={m.id} className={`msg ${m.role}`}>
                {m.role === "assistant" ? (
                  <>
                    <AnswerText text={m.content} onCite={(n) => onCite(m, n)} />
                    {m.covered === false && (
                      <div className="flag not-covered">⚠ Not covered in the provided transcripts</div>
                    )}
                    {m.covered === true && (
                      <div className="flag grounded">✓ Grounded · {m.citations.length} citations</div>
                    )}
                  </>
                ) : (
                  m.content
                )}
              </div>
            ))}
            {busy && (
              <div className="thinking">
                <span className="pulse" /> Agent working — rewrite → retrieve → grade → answer…
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {error && <div className="error-banner">{error}</div>}

          <div className="presets">
            {presets.map((q) => (
              <button key={q} className="preset" onClick={() => ask(q)} disabled={busy}>
                {q}
              </button>
            ))}
          </div>
          <div className="composer">
            <input
              value={input}
              placeholder="Ask anything about the interviews…"
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && ask(input)}
              disabled={busy}
            />
            <button onClick={() => ask(input)} disabled={busy || !input.trim()}>
              Ask
            </button>
          </div>
        </main>

        <ReferencesPanel
          citations={selectedMsg?.citations ?? []}
          trace={selectedMsg?.trace ?? []}
          tab={tab}
          setTab={setTab}
          highlighted={highlighted}
        />
      </div>
    </>
  );
}
