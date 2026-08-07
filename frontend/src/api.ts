import type { AskResponse, Health, Message, Session } from "./types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? res.statusText);
  }
  return res.json();
}

export const api = {
  health: () => fetch("/api/health").then((r) => json<Health>(r)),
  presets: () =>
    fetch("/api/presets").then((r) => json<{ questions: string[] }>(r)),
  listSessions: () => fetch("/api/sessions").then((r) => json<Session[]>(r)),
  createSession: (title = "New session") =>
    fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    }).then((r) => json<Session>(r)),
  renameSession: (sessionId: string, title: string) =>
    fetch(`/api/sessions/${sessionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    }).then((r) => json<{ ok: boolean }>(r)),
  deleteSession: (sessionId: string) =>
    fetch(`/api/sessions/${sessionId}`, { method: "DELETE" }).then((r) =>
      json<{ ok: boolean }>(r),
    ),
  getMessages: (sessionId: string) =>
    fetch(`/api/sessions/${sessionId}/messages`).then((r) => json<Message[]>(r)),
  ask: (sessionId: string, question: string) =>
    fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, question }),
    }).then((r) => json<AskResponse>(r)),
};
