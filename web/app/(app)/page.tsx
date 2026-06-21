"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { streamChat } from "@/lib/sse";
import Composer from "@/components/composer/Composer";

// FRONTEND_NEXTJS_SPEC §6.0 (랜딩 hero) ↔ §6.1 (워크스페이스).
// 사용자 외부 분석: Lovable 70 / ChatGPT 20 / FigureLabs 10.
// 빈 상태 = 딥블루 메시 그라데이션 hero + 5 추천 카드 + 중앙 큰 입력박스.
// 첫 send → AnimatePresence로 워크스페이스 슬라이드 전환.

type Msg = { role: "user" | "assistant"; content: string };
type Trace = { kind: "status" | "tool_start" | "tool_result"; text: string; done?: boolean };

const SUGGESTIONS = [
  {
    title: "KNHANES Analysis",
    desc: "국건영 12 wave · survey-weighted",
    icon: "📊",
    prompt: "KNHANES 2023 데이터로 UPF 섭취와 MASLD 연관성 분석해줘",
  },
  {
    title: "Meta-analysis",
    desc: "체계적 문헌고찰 + 효과크기 통합",
    icon: "🔬",
    prompt: "MASLD 유병률 메타분석을 시작하고 싶어. PICO부터 정리해줘",
  },
  {
    title: "Cohort Study",
    desc: "추적 코호트 설계 + GEE/생존",
    icon: "📈",
    prompt: "청소년 우울 코호트 설계 — KYRBS 다년 추적으로 가능한 노출 후보를 정리해줘",
  },
  {
    title: "Systematic Review",
    desc: "PRISMA flow + Risk of Bias",
    icon: "📚",
    prompt: "지방간 신정의 (MASLD 2023) 체계적 문헌고찰 — search query + flow 만들어줘",
  },
  {
    title: "Manuscript Draft",
    desc: "IMRaD + EndNote + Forest plot",
    icon: "📄",
    prompt: "기존 분석 결과를 바탕으로 Introduction과 Methods 초안 양식 써줘",
  },
];

export default function AppPage() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [trace, setTrace] = useState<Trace[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [phase, setPhase] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, trace]);

  async function send(msg: string, attachments?: File[]) {
    if (!msg.trim() || streaming) return;
    const attachNote = attachments && attachments.length > 0
      ? `📎 ${attachments.map((f) => f.name).join(", ")}\n\n` : "";
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
      setMessages((m) => [...m, { role: "assistant",
        content: `⚠ 연결 실패: ${String(e).slice(0, 120)}` }]);
    } finally {
      setStreaming(false);
      setPhase("");
    }
  }

  const isLanding = messages.length === 0;

  return (
    <AnimatePresence mode="wait" initial={false}>
      {isLanding ? (
        <motion.section
          key="landing"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, scale: 0.98 }}
          transition={{ duration: 0.45, ease: [0.4, 0, 0.2, 1] }}
          className="relative flex-1 overflow-hidden"
        >
          {/* 메시 그라데이션 배경 (딥블루 오로라) */}
          <div className="absolute inset-0 -z-10"
               style={{
                 background:
                   "radial-gradient(60% 50% at 20% 20%, rgba(47,94,255,0.35), transparent 60%)," +
                   "radial-gradient(55% 45% at 80% 25%, rgba(124,58,237,0.22), transparent 60%)," +
                   "radial-gradient(70% 60% at 50% 100%, rgba(236,72,153,0.18), transparent 65%)," +
                   "radial-gradient(60% 50% at 10% 90%, rgba(6,182,212,0.18), transparent 55%)," +
                   "linear-gradient(180deg, #0B1020 0%, #122B5E 65%, #0B1020 100%)",
                 filter: "saturate(115%)",
               }} />
          {/* 노이즈/그레인 (싸구려 그라데이션 양식 차단) */}
          <div className="absolute inset-0 -z-10 opacity-[0.07] mix-blend-overlay"
               style={{
                 backgroundImage:
                   "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='200' height='200' filter='url(%23n)'/></svg>\")",
               }} />
          {/* knowledge graph 추상 (저투명도) */}
          <svg className="absolute inset-0 -z-10 w-full h-full opacity-[0.08]"
               viewBox="0 0 1200 700" fill="none" stroke="white" strokeWidth="0.5">
            <g>
              <line x1="120" y1="180" x2="320" y2="240" />
              <line x1="320" y1="240" x2="520" y2="160" />
              <line x1="520" y1="160" x2="700" y2="280" />
              <line x1="700" y1="280" x2="880" y2="200" />
              <line x1="880" y1="200" x2="1060" y2="320" />
              <line x1="320" y1="240" x2="280" y2="460" />
              <line x1="280" y1="460" x2="480" y2="540" />
              <line x1="480" y1="540" x2="700" y2="280" />
              <line x1="700" y1="280" x2="820" y2="500" />
              <line x1="820" y1="500" x2="1000" y2="420" />
              {[
                [120, 180], [320, 240], [520, 160], [700, 280], [880, 200],
                [1060, 320], [280, 460], [480, 540], [820, 500], [1000, 420],
              ].map(([x, y], i) => (
                <circle key={i} cx={x} cy={y} r={i % 3 === 0 ? 3 : 2} fill="white" />
              ))}
            </g>
          </svg>

          {/* Hero 본문 */}
          <div className="relative h-full flex flex-col items-center justify-center px-6 py-12">
            <motion.div
              initial={{ y: 14, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.05, duration: 0.45, ease: [0.4, 0, 0.2, 1] }}
              className="w-full max-w-3xl"
            >
              {/* 떠 있는 pill 배지 */}
              <div className="flex justify-center mb-6">
                <div className="inline-flex items-center gap-2 px-3 py-1.5
                                  rounded-full bg-white/10 backdrop-blur-md
                                  border border-white/15 text-[0.7rem] text-white/80">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  KYRBS · KNHANES · PubMed 24K 연결됨
                </div>
              </div>

              <h1 className="text-center text-white font-semibold tracking-tight
                              text-[clamp(2rem,5vw,3.5rem)] leading-[1.1]">
                Medical <span className="bg-gradient-to-r from-white to-white/70 bg-clip-text text-transparent">Research Agent</span>
              </h1>
              <p className="text-center text-white/65 mt-4 text-sm md:text-base">
                Transform questions into evidence, analysis and publications.
              </p>

              {/* 큰 입력박스 (떠 있는 다크 글래스) */}
              <div className="mt-10">
                <HeroInput onSend={(t) => send(t, [])} disabled={streaming} />
              </div>

              {/* 5 추천 카드 */}
              <div className="mt-7 grid grid-cols-2 md:grid-cols-5 gap-2.5">
                {SUGGESTIONS.map((s, i) => (
                  <motion.button
                    key={s.title}
                    initial={{ y: 10, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ delay: 0.15 + i * 0.04, duration: 0.35,
                                    ease: [0.4, 0, 0.2, 1] }}
                    onClick={() => send(s.prompt, [])}
                    className="group text-left px-3.5 py-3 rounded-2xl
                                  bg-white/[0.06] backdrop-blur-md
                                  border border-white/10
                                  hover:bg-white/[0.10] hover:border-white/20 hover:-translate-y-0.5
                                  transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]"
                  >
                    <div className="text-base mb-1.5">{s.icon}</div>
                    <div className="text-[0.78rem] font-medium text-white leading-snug">
                      {s.title}
                    </div>
                    <div className="text-[0.65rem] text-white/55 mt-0.5 leading-snug">
                      {s.desc}
                    </div>
                  </motion.button>
                ))}
              </div>
            </motion.div>
          </div>
        </motion.section>
      ) : (
        <motion.div
          key="workspace"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
          className="flex-1 flex flex-col overflow-hidden"
        >
          <div className="flex-1 overflow-y-auto px-6 py-8">
            <div className="max-w-3xl mx-auto space-y-5">
              {messages.map((m, i) => (
                <div key={i} className={"anim-slide-in " +
                  (m.role === "user" ? "flex justify-end" : "flex justify-start")}>
                  <div className={
                    m.role === "user"
                      ? "max-w-[80%] rounded-2xl rounded-tr-md bg-sapphire text-white px-4 py-3 " +
                        "text-[0.92rem] leading-[1.6] whitespace-pre-wrap shadow-[0_2px_8px_rgba(31,78,121,0.18)]"
                      : "max-w-[85%] rounded-2xl rounded-tl-md bg-white border border-ink/5 px-5 py-4 " +
                        "text-[0.93rem] leading-[1.7] whitespace-pre-wrap text-ink " +
                        "shadow-[0_1px_2px_rgba(34,34,34,0.04),0_8px_24px_rgba(34,34,34,0.04)]"
                  }>
                    {m.content}
                    {m.role === "assistant" && streaming && i === messages.length - 1 && (
                      <span className="stream-cursor" />
                    )}
                  </div>
                </div>
              ))}

              {streaming && (phase || trace.length > 0) && (
                <div className="anim-slide-in flex justify-start">
                  <div className="max-w-[85%] think-card">
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
                    {trace.length > 0 && (
                      <ol className="space-y-1 mt-2">
                        {trace.slice(-6).map((t, i) => (
                          <li key={i} className="flex items-start gap-2 text-[0.75rem]">
                            <span className={
                              "mt-1 w-1 h-1 rounded-full flex-shrink-0 " +
                              (t.kind === "tool_start" && !t.done
                                ? "bg-warning animate-pulse"
                                : t.kind === "tool_result" || t.done
                                ? "bg-success" : "bg-sapphire/60")
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
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// 큰 hero 입력박스 (떠 있는 다크 글래스)
function HeroInput({ onSend, disabled }: { onSend: (t: string) => void; disabled: boolean }) {
  const [text, setText] = useState("");
  function go() {
    const t = text.trim();
    if (!t || disabled) return;
    onSend(t);
    setText("");
  }
  return (
    <div className="relative">
      <div className="rounded-3xl bg-white/[0.07] backdrop-blur-2xl
                        border border-white/15
                        shadow-[0_20px_50px_-12px_rgba(0,0,0,0.6),0_8px_24px_-8px_rgba(47,94,255,0.25)]
                        px-4 py-3 flex items-end gap-3">
        <button className="text-white/55 hover:text-white transition-colors p-1.5"
                aria-label="첨부">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 10a9 9 0 1 1-18 0V8a4 4 0 0 1 8 0v8a3 3 0 1 1-6 0V10" />
          </svg>
        </button>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              go();
            }
          }}
          rows={1}
          placeholder="Ask a research question…"
          className="flex-1 resize-none bg-transparent outline-none text-white
                       placeholder:text-white/40 text-[0.95rem] py-1.5 max-h-32"
        />
        <button
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full
                       bg-white/10 hover:bg-white/15 border border-white/15 text-white/85
                       text-[0.72rem] transition-colors"
        >
          Build
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2.5" strokeLinecap="round">
            <path d="M6 9l6 6 6-6" />
          </svg>
        </button>
        <button onClick={go} disabled={disabled || !text.trim()}
                className="w-9 h-9 rounded-full bg-white text-sapphire-900
                              flex items-center justify-center
                              shadow-[0_4px_14px_rgba(255,255,255,0.25)]
                              hover:shadow-[0_6px_20px_rgba(255,255,255,0.35)]
                              hover:-translate-y-0.5
                              disabled:opacity-40 disabled:translate-y-0
                              transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 19V5M5 12l7-7 7 7" />
          </svg>
        </button>
      </div>
      <div className="mt-2 text-center text-[0.7rem] text-white/45">
        Enter 전송 · Shift+Enter 줄바꿈 · 첨부 가능
      </div>
    </div>
  );
}
