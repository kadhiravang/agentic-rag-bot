export interface Citation {
  marker: number;
  source: string;
  speakers: string[];
  ts_start: string;
  ts_end: string;
  page_start: number;
  page_end: number;
  quote: string;
  chunk_id: string;
  score: number;
}

export interface TraceStep {
  step: string;
  detail: string;
  retry?: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  covered: boolean | null;
  citations: Citation[];
  trace: TraceStep[];
  created_at: string;
}

export interface Session {
  id: string;
  username: string;
  title: string;
  created_at: string;
}

export interface AskResponse {
  message_id: string;
  answer: string;
  covered: boolean;
  citations: Citation[];
  trace: TraceStep[];
}

export interface Health {
  status: string;
  user: string;
  vector_store: { indexed: boolean; points: number };
  answer_model: string;
  grader_model: string;
}
