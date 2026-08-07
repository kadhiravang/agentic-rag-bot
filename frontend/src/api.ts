import type { AskResponse, Health, Message, Session, SessionFile } from "./types";

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
  listFiles: (sessionId: string) =>
    fetch(`/api/sessions/${sessionId}/files`).then((r) => json<SessionFile[]>(r)),
  loadDefaults: (sessionId: string) =>
    fetch(`/api/sessions/${sessionId}/load-defaults`, { method: "POST" }).then((r) =>
      json<SessionFile[]>(r),
    ),
  uploadFile: (sessionId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`/api/sessions/${sessionId}/files`, {
      method: "POST",
      body: form,
    }).then((r) => json<SessionFile>(r));
  },
  ask: (sessionId: string, question: string) =>
    fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, question }),
    }).then((r) => json<AskResponse>(r)),
};
