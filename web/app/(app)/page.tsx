"use client";

import { useState, useRef, useEffect } from "react";
import { streamChat } from "@/lib/sse";
import Composer from "@/components/composer/Composer";

// FRONTEND_NEXTJS_SPEC §6: 채팅 본문 + 사고 트레이스. 2026-06-21 — Composer 컴포넌트 사용 (첨부 자리 살아남).
export default function AppPage() {
  const [messages, setMessages] = useState<Array<{ role: "user" | "assistant"; content: string }>>([]);
  const [trace, setTrace] = useState<Array<{ kind: string; text: string }>>([]);
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(msg: string, attachments?: File[]) {
    if (!msg.trim() || streaming) return;

    // 첨부 표시 (1차 — 파일명만 메시지에 prepend. multipart 전송은 다음 사이클)
    const attachNote = attachments && attachments.length > 0
      ? `📎 ${attachments.map(f => f.name).join(", ")}\n\n`
      : "";
    const fullMsg = attachNote + msg;

    setMessages((m) => [...m, { role: "user", content: fullMsg }]);
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
      setMessages((m) => [...m, { role: "assistant", content: `[연결 실패: ${String(e).slice(0, 120)}]` }]);
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
            연구 아이디어를 한 줄로 적어보세요. <br />
            <span className="text-xs text-ink-muted">예: KNHANES UPF × MASLD · KYRBS 청소년 우울 · 카페인 대사증후군</span>
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={
              m.role === "user"
                ? "ml-auto max-w-2xl bg-sapphire/10 rounded-xl px-4 py-3 text-ink whitespace-pre-wrap"
                : "mr-auto max-w-2xl bg-white rounded-xl px-4 py-3 shadow-sm border border-ink-muted/10 text-ink whitespace-pre-wrap"
            }
          >
            {m.content}
          </div>
        ))}

        {/* 사고 트레이스 */}
        {trace.length > 0 && (
          <details className="mr-auto max-w-2xl text-sm text-ink-subtle bg-surface-alt rounded-lg px-3 py-2 border border-ink-muted/10">
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

      <Composer onSend={send} disabled={streaming} />
    </>
  );
}
