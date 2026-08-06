import type { Citation, TraceStep } from "../types";

interface Props {
  citations: Citation[];
  trace: TraceStep[];
  tab: "refs" | "trace";
  setTab: (t: "refs" | "trace") => void;
  highlighted: number | null;
}

const STEP_LABELS: Record<string, string> = {
  rewrite_query: "Query rewrite",
  retrieve: "Vector retrieval (Qdrant)",
  grade: "Relevance grading",
  answer: "Grounded answer",
  not_covered: "Refusal (not covered)",
};

export function ReferencesPanel({ citations, trace, tab, setTab, highlighted }: Props) {
  return (
    <aside className="refs">
      <div className="tabs">
        <div className={`tab ${tab === "refs" ? "active" : ""}`} onClick={() => setTab("refs")}>
          References ({citations.length})
        </div>
        <div className={`tab ${tab === "trace" ? "active" : ""}`} onClick={() => setTab("trace")}>
          Agent trace
        </div>
      </div>
      <div className="body">
        {tab === "refs" &&
          (citations.length === 0 ? (
            <div className="hint">
              Citations for the selected answer appear here — who said it, when
              (timestamp), and where (transcript + page).
            </div>
          ) : (
            citations.map((c) => (
              <div
                key={c.marker}
                id={`ref-${c.marker}`}
                className={`ref-card ${highlighted === c.marker ? "highlight" : ""}`}
              >
                <div className="top">
                  <span className="marker">[{c.marker}]</span>
                  <span className="source">{c.source}</span>
                </div>
                <div className="meta">
                  <span>🗣 {c.speakers.join(", ")}</span>
                  <span>⏱ {c.ts_start}–{c.ts_end}</span>
                  <span>
                    📄 p.{c.page_start}
                    {c.page_end !== c.page_start ? `–${c.page_end}` : ""}
                  </span>
                  <span>score {c.score.toFixed(2)}</span>
                </div>
                <blockquote>“{c.quote}”</blockquote>
              </div>
            ))
          ))}
        {tab === "trace" &&
          (trace.length === 0 ? (
            <div className="hint">
              The agent's reasoning steps (rewrite → retrieve → grade → answer)
              appear here after each question.
            </div>
          ) : (
            trace.map((s, i) => (
              <div className="trace-step" key={i}>
                <div className="n">{i + 1}</div>
                <div className="txt">
                  <b>
                    {STEP_LABELS[s.step] ?? s.step}
                    {s.retry ? ` (retry ${s.retry})` : ""}
                  </b>
                  <span>{s.detail}</span>
                </div>
              </div>
            ))
          ))}
      </div>
    </aside>
  );
}
