// FRONTEND_MIGRATION_SPEC §5.5.6 — SSE consumer.
// /chat POST → text/event-stream. 각 frame = `data: {"type":..., "data":..., "seq":N}\n\n`
// ChatEvent generator를 그대로 흘려보내는 src.service.chat.stream_turn 호환.

import { apiUrl } from "./api";

export type ChatEvent = {
  type:
    | "status"
    | "plan"
    | "tool_start"
    | "tool_result"
    | "token"
    | "section_done"
    | "warning"
    | "badge"
    | "done"
    | "error";
  data: Record<string, unknown> & { msg?: string; tool?: string; text?: string };
  seq?: number;
  ts?: number;
};

export async function* streamChat(opts: {
  message: string;
  project_id?: string;
  max_tokens?: number;
}): AsyncIterable<ChatEvent> {
  const res = await fetch(apiUrl("/chat"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      message: opts.message,
      project_id: opts.project_id,
      max_tokens: opts.max_tokens ?? 2048,
    }),
  });
  if (!res.body) throw new Error("SSE body missing");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let nlIdx;
    while ((nlIdx = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, nlIdx);
      buffer = buffer.slice(nlIdx + 2);
      const lines = frame.split("\n");
      const dataLine = lines.find((l) => l.startsWith("data: "));
      if (!dataLine) continue;
      try {
        const ev = JSON.parse(dataLine.slice(6)) as ChatEvent;
        yield ev;
        if (ev.type === "done") return;
      } catch {
        // skip malformed frame
      }
    }
  }
}
