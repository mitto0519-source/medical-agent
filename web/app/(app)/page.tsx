"use client";

import { useState, useRef, useEffect } from "react";
import { streamChat } from "@/lib/sse";

// FRONTEND_NEXTJS_SPEC §6 + AGENT_OUTPUT_UX_SPEC §2/§3 골격.
// Phase 3 — 채팅 본문 + 사고 트레이스 expander + 컴포저.
export default function AppPage() {
  const [messages, setMessages] = useState<Array<{ role: "user" | "assistant"; content: string }>>([]);
  const [trace, setTrace] = useState<Array<{ kind: string; text: string }>>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send() {
    const msg = input.trim();
    if (!msg || streaming) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: msg }]);
    setTrace([]);
    setStreaming(true);

    let body = "";
    try {
      for await (const ev of streamChat({ message: msg })) {
        if (ev.type === "status") setTrace((t) => [...t, { kind: "status", text: ev.data?.msg || "" }]);
        else if (ev.type === "tool_start") setTrace((t) => [...t, { kind: "tool_start", text: ev.data?.tool || "" }]);
        else if (ev.type === "tool_result") setTrace((t) => [...t, { kind: "tool_result", text: ev.data?.tool || "" }]);
        else if (ev.type === "token") {
          body += ev.data?.text || "";
          setMessages((m) => {
            const last = m[m.length - 1];
            if (last?.role === "assistant") {
              return [...m.slice(0, -1), { role: "assistant", content: body }];
            }
            return [...m, { role: "assistant", content: body }];
          });
        }
      }
    } catch (e) {
      console.warn("stream fail", e);
    } finally {
      setStreaming(false);
    }
  }

  return (
    <>
      {/* 메시지 로그 */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-ink-subtle text-sm py-20">
            연구 아이디어를 한 줄로 적어보세요.
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={
              m.role === "user"
                ? "ml-auto max-w-2xl bg-sapphire-50 rounded-xl px-4 py-3 text-ink"
                : "mr-auto max-w-2xl bg-white rounded-xl px-4 py-3 shadow-glass text-ink"
            }
          >
            {m.content}
          </div>
        ))}

        {/* 사고 트레이스 (AGENT_OUTPUT_UX §2) */}
        {trace.length > 0 && (
          <details className="mr-auto max-w-2xl text-sm text-ink-subtle bg-surface-alt rounded-lg px-3 py-2">
            <summary className="cursor-pointer">🧠 사고 과정 ({trace.length} 단계)</summary>
            <ol className="mt-2 space-y-1 list-decimal pl-4">
              {trace.slice(-20).map((t, i) => (
                <li key={i}>
                  {t.kind === "status" && <span>💭 {t.text}</span>}
                  {t.kind === "tool_start" && <span>🔧 <b>{t.text}</b></span>}
                  {t.kind === "tool_result" && <span>✓ {t.text}</span>}
                </li>
              ))}
            </ol>
          </details>
        )}
        <div ref={bottomRef} />
      </div>

      {/* 컴포저 (UX_CHAT_DESIGN §4: 단일 박스, 첨부칩·모델·@ref 내장) */}
      <div className="border-t border-ink-muted/15 bg-white p-4">
        <div className="max-w-3xl mx-auto flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), send())}
            disabled={streaming}
            placeholder="MASLD vs MetALD 정의를 비교하고 싶어… 같이"
            className="flex-1 px-4 py-2.5 border border-ink-muted/20 rounded-md text-sm focus:border-sapphire outline-none"
          />
          <button
            onClick={send}
            disabled={streaming || !input.trim()}
            className="px-5 py-2.5 bg-sapphire text-white rounded-md text-sm font-medium disabled:opacity-50"
          >
            {streaming ? "..." : "↑"}
          </button>
        </div>
      </div>
    </>
  );
}
