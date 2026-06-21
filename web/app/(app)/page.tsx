"use client";

import { useState, useRef, useEffect } from "react";
import { streamChat } from "@/lib/sse";
import Composer from "@/components/composer/Composer";

// FRONTEND_NEXTJS_SPEC §6 + AGENT_OUTPUT_UX_SPEC §2: 채팅 본문.
// 2026-06-21 v2 강화 (사용자 정직 '껍데기 양식'):
//   · 사고 과정 시각화 (단계별 진행 카드, 펄스 활성, tool 호출 표시)
//   · 토큰 스트리밍 커서 효과
//   · 환영 화면 예시 chip + 사용 가이드
//   · 메시지 카드 (그림자 + slide-in)

type Msg = { role: "user" | "assistant"; content: string };
type Trace = { kind: "status" | "tool_start" | "tool_result"; text: string; done?: boolean };

const EXAMPLE_TOPICS = [
  "KNHANES UPF × MASLD",
  "KYRBS 청소년 우울",
  "카페인 대사증후군",
  "지방간 신정의 2023",
];

export default function AppPage() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [trace, setTrace] = useState<Trace[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [phase, setPhase] = useState<string>("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, trace]);

  async function send(msg: string, attachments?: File[]) {
    if (!msg.trim() || streaming) return;

    const attachNote = attachments && attachments.length > 0
      ? `📎 ${attachments.map(f => f.name).join(", ")}\n\n`
      : "";

    setMessages((m) => [...m, { role: "user", content: attachNote + msg }]);
    setTrace([]);
    setPhase("이해 중");
    setStreaming(true);

    let body = "";
    try {
      for await (const ev of streamChat({ message: msg })) {
        if (ev.type === "status") {
          const t = (ev.data?.msg as string) || "";
          setPhase(t);
          setTrace((tr) => [...tr.map((x) => ({ ...x, done: true })),
                              { kind: "status", text: t }]);
        } else if (ev.type === "tool_start") {
          const t = (ev.data?.tool as string) || "";
          setPhase(`${t} 호출 중`);
          setTrace((tr) => [...tr.map((x) => ({ ...x, done: true })),
                              { kind: "tool_start", text: t }]);
        } else if (ev.type === "tool_result") {
          const t = (ev.data?.tool as string) || "";
          setTrace((tr) => tr.map((x) =>
            x.kind === "tool_start" && x.text === t && !x.done
              ? { ...x, done: true } : x));
        } else if (ev.type === "token") {
          body += (ev.data?.text as string) || "";
          setPhase("");
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
      setMessages((m) => [...m, {
        role: "assistant",
        content: `⚠ 연결 실패: ${String(e).slice(0, 120)}`
      }]);
    } finally {
      setStreaming(false);
      setPhase("");
    }
  }

  function pickExample(t: string) {
    send(t, []);
  }

  const hasMsgs = messages.length > 0;

  return (
    <>
      {/* 메시지 로그 */}
      <div className="flex-1 overflow-y-auto px-6 py-8">
        <div className="max-w-3xl mx-auto space-y-5">
          {/* 환영 화면 */}
          {!hasMsgs && (
            <div className="anim-slide-in mt-8">
              <div className="text-center mb-8">
                <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl
                                  bg-gradient-to-br from-sapphire/15 to-sapphire/5
                                  border border-sapphire/10 mb-5">
                  <span className="text-2xl">🔬</span>
                </div>
                <h1 className="text-[1.35rem] font-semibold tracking-tight text-ink mb-2">
                  무엇을 연구하시겠어요?
                </h1>
                <p className="text-sm text-ink-subtle leading-relaxed">
                  한 줄로 적어주세요 — PICO · 변수 · 통계 · 신규성까지 정리해드립니다.
                </p>
              </div>

              {/* 예시 chip — DESIGN-LANGUAGE §5 pill, hover lift */}
              <div className="flex flex-wrap justify-center gap-2">
                {EXAMPLE_TOPICS.map((t) => (
                  <button
                    key={t}
                    onClick={() => pickExample(t)}
                    className="group px-3.5 py-2 rounded-full bg-white border border-ink/8
                                 text-xs text-ink-subtle
                                 shadow-[0_1px_2px_rgba(34,34,34,0.04)]
                                 hover:border-sapphire/30 hover:text-sapphire hover:-translate-y-0.5
                                 hover:shadow-[0_4px_12px_rgba(31,78,121,0.08)]
                                 transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]"
                  >
                    <span className="opacity-50 mr-1.5 group-hover:opacity-100 transition-opacity">💡</span>
                    {t}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 대화 */}
          {messages.map((m, i) => (
            <div key={i} className={
              "anim-slide-in " +
              (m.role === "user" ? "flex justify-end" : "flex justify-start")
            }>
              <div
                className={
                  m.role === "user"
                    ? "max-w-[80%] rounded-2xl rounded-tr-md bg-sapphire text-white px-4 py-3 " +
                      "text-[0.92rem] leading-[1.6] whitespace-pre-wrap shadow-[0_2px_8px_rgba(31,78,121,0.18)]"
                    : "max-w-[85%] rounded-2xl rounded-tl-md bg-white border border-ink/5 px-5 py-4 " +
                      "text-[0.93rem] leading-[1.7] whitespace-pre-wrap text-ink " +
                      "shadow-[0_1px_2px_rgba(34,34,34,0.04),0_8px_24px_rgba(34,34,34,0.04)]"
                }
              >
                {m.content}
                {m.role === "assistant" && streaming && i === messages.length - 1 && (
                  <span className="stream-cursor" />
                )}
              </div>
            </div>
          ))}

          {/* 사고 과정 카드 — 응답 중 단계별 진행 */}
          {streaming && (phase || trace.length > 0) && (
            <div className="anim-slide-in flex justify-start">
              <div className="max-w-[85%] think-card">
                {/* 헤더 */}
                <div className="flex items-center gap-2.5 mb-2">
                  <div className="flex gap-1">
                    <span className="pulse-dot" style={{ animationDelay: "0ms" }} />
                    <span className="pulse-dot" style={{ animationDelay: "200ms" }} />
                    <span className="pulse-dot" style={{ animationDelay: "400ms" }} />
                  </div>
                  <div className="text-[0.78rem] font-medium text-sapphire">
                    {phase || "생각 중"}
                  </div>
                  <span className="text-[0.68rem] text-ink-muted ml-auto tabular-nums">
                    step {trace.length}
                  </span>
                </div>

                {/* 단계 리스트 */}
                {trace.length > 0 && (
                  <ol className="space-y-1 mt-2">
                    {trace.slice(-6).map((t, i) => (
                      <li key={i} className="flex items-start gap-2 text-[0.75rem] leading-relaxed">
                        <span className={
                          "mt-1 w-1 h-1 rounded-full flex-shrink-0 " +
                          (t.kind === "tool_start" && !t.done
                            ? "bg-warning animate-pulse"
                            : t.kind === "tool_result" || t.done
                            ? "bg-success"
                            : "bg-sapphire/60")
                        } />
                        <span className={t.done ? "text-ink-muted" : "text-ink-subtle"}>
                          {t.kind === "tool_start" && "🔧 "}
                          {t.kind === "tool_result" && "✓ "}
                          {t.kind === "status" && "· "}
                          {t.text || "—"}
                        </span>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      <Composer onSend={send} disabled={streaming} />
    </>
  );
}
