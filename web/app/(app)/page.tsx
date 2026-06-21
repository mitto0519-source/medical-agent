"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { streamChat } from "@/lib/sse";
import Composer from "@/components/composer/Composer";
import ChatMessage from "@/components/ChatMessage";
import InlineFigure from "@/components/InlineFigure";

// CRAFT_SPEC §13 적응 + 사용자 정직 요구:
//   진입(messages=0) = 딥네이비 hero(L0+L1 atmosphere) + 5 추천 카드 + Surface C 입력박스
//   작업(messages>0) = 라이트 톤(FigureLabs §6.4) + Lovable 채팅 craft (인라인 figure + 액션)
//
// 채팅: 최신 메시지가 자동 하단 고정 (overflow-y-auto + scroll bottom)
// 응답 중간 이미지: Block[] 양식 — text/figure/code 인라인 양식

type Block = { kind: "text"; text: string }
            | { kind: "figure"; title: string; caption?: string; src?: string; engine?: string; state: "loading" | "ready" | "error" };
type Msg = { role: "user" | "assistant"; blocks: Block[] };
type Trace = { kind: "status" | "tool_start" | "tool_result"; text: string; done?: boolean };

const SUGGESTIONS = [
  { title: "KNHANES Analysis", desc: "Survey-weighted, ready to run", icon: "📊",
    prompt: "KNHANES 2023 데이터로 UPF 섭취와 MASLD 연관성 분석해줘" },
  { title: "Meta-analysis", desc: "Pooled effects + forest plot", icon: "⊕",
    prompt: "MASLD 유병률 메타분석을 시작하고 싶어. PICO부터 정리해줘" },
  { title: "Cohort Study", desc: "KM · Cox · person-years", icon: "◷",
    prompt: "청소년 우울 코호트 설계 — KYRBS 다년 추적으로 가능한 노출 후보 정리해줘" },
  { title: "Systematic Review", desc: "PRISMA-guided screening", icon: "📚",
    prompt: "지방간 신정의(MASLD 2023) 체계적 문헌고찰 — search query + flow 만들어줘" },
  { title: "Manuscript Draft", desc: "Cho-style, journal-ready", icon: "✎",
    prompt: "기존 분석 결과를 바탕으로 Introduction과 Methods 초안을 써줘" },
];

export default function AppPage() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [trace, setTrace] = useState<Trace[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [phase, setPhase] = useState("");
  const userName = "수수"; // TODO: /me에서 가져옴
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, trace]);

  function appendText(role: "user" | "assistant", text: string) {
    setMessages((m) => [...m, { role, blocks: [{ kind: "text", text }] }]);
  }
  function updateLastAssistantText(text: string) {
    setMessages((m) => {
      if (m.length === 0 || m[m.length - 1].role !== "assistant") {
        return [...m, { role: "assistant", blocks: [{ kind: "text", text }] }];
      }
      const last = m[m.length - 1];
      const blocks = [...last.blocks];
      const lastBlockIdx = blocks.length - 1;
      if (blocks[lastBlockIdx]?.kind === "text") {
        blocks[lastBlockIdx] = { kind: "text", text };
      } else {
        blocks.push({ kind: "text", text });
      }
      return [...m.slice(0, -1), { ...last, blocks }];
    });
  }

  async function send(rawMsg: string, attachments?: File[]) {
    if (!rawMsg.trim() || streaming) return;
    const attachNote = attachments && attachments.length > 0
      ? `📎 ${attachments.map((f) => f.name).join(", ")}\n\n` : "";
    appendText("user", attachNote + rawMsg);
    setTrace([]);
    setPhase("이해 중");
    setStreaming(true);

    let body = "";
    try {
      for await (const ev of streamChat({ message: rawMsg })) {
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
          updateLastAssistantText(body);
        }
      }
    } catch (e) {
      appendText("assistant", `⚠ 연결 실패: ${String(e).slice(0, 120)}`);
    } finally {
      setStreaming(false);
      setPhase("");
    }
  }

  const isLanding = messages.length === 0;

  return (
    <AnimatePresence mode="wait" initial={false}>
      {isLanding ? (
        /* ★ Hero (L0 + L1 atmosphere + Surface C 입력박스) */
        <motion.section
          key="landing"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, scale: 0.98 }}
          transition={{ duration: 0.45, ease: [0.4, 0, 0.2, 1] }}
          className="relative flex-1 overflow-hidden"
          style={{ background: "#09090B" }}
        >
          {/* L1 atmosphere — 메시 그라데이션 (4 blobs + blur 120 + drift) */}
          <div className="atmosphere" />
          {/* knowledge graph 추상 (저투명) */}
          <svg className="absolute inset-0 w-full h-full opacity-[0.06] pointer-events-none z-[1]"
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
              {[[120,180],[320,240],[520,160],[700,280],[880,200],
                [1060,320],[280,460],[480,540],[820,500],[1000,420]
              ].map(([x, y], i) => (
                <circle key={i} cx={x} cy={y} r={i % 3 === 0 ? 3 : 2} fill="white" />
              ))}
            </g>
          </svg>

          <div className="relative z-10 h-full flex flex-col items-center justify-center px-6">
            <motion.div
              initial={{ y: 14, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.05, duration: 0.45, ease: [0.4, 0, 0.2, 1] }}
              className="w-full max-w-[720px]"
            >
              {/* Floating pill 배지 */}
              <div className="flex justify-center mb-7">
                <div className="floating-pill">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-300"
                        style={{ boxShadow: "0 0 8px #22D3EE" }} />
                  <span style={{ color: "var(--txt-secondary)" }}>
                    Connected to KNHANES · KYRBS · PubMed 24K
                  </span>
                </div>
              </div>

              {/* 헤드라인 — 개인화 (Ready to research, [name]?) */}
              <h1 className="text-center text-white font-bold tracking-tight
                              text-[clamp(2.2rem,5vw,3.4rem)] leading-[1.05]">
                Ready to research, <span className="bg-gradient-to-r from-white to-white/70 bg-clip-text text-transparent">{userName}?</span>
              </h1>
              <p className="text-center mt-4 text-[0.97rem] leading-relaxed"
                 style={{ color: "var(--txt-secondary)" }}>
                Transform questions into evidence, analysis and publications.
              </p>

              {/* Surface C 입력박스 — radius 28, padding 20×22, border .08 */}
              <div className="mt-10">
                <HeroInput onSend={(t) => send(t, [])} disabled={streaming} />
              </div>

              {/* 5 추천 카드 — Surface A · gap 12 · radius 16 */}
              <div className="mt-7 grid grid-cols-2 md:grid-cols-5 gap-3">
                {SUGGESTIONS.map((s, i) => (
                  <motion.button
                    key={s.title}
                    initial={{ y: 10, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ delay: 0.15 + i * 0.04, duration: 0.35,
                                    ease: [0.4, 0, 0.2, 1] }}
                    onClick={() => send(s.prompt, [])}
                    className="group text-left px-3.5 py-3 rounded-2xl
                                  transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]"
                    style={{
                      background: "var(--surface-a)",
                      border: "1px solid var(--border)",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "var(--surface-b)";
                      e.currentTarget.style.borderColor = "var(--border-hover)";
                      e.currentTarget.style.transform = "translateY(-2px)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "var(--surface-a)";
                      e.currentTarget.style.borderColor = "var(--border)";
                      e.currentTarget.style.transform = "translateY(0)";
                    }}
                  >
                    <div className="text-base mb-1.5" style={{ color: "var(--txt-secondary)" }}>
                      {s.icon}
                    </div>
                    <div className="text-[0.8rem] font-medium leading-snug text-white">
                      {s.title}
                    </div>
                    <div className="text-[0.66rem] mt-0.5 leading-snug"
                         style={{ color: "var(--txt-muted)" }}>
                      {s.desc}
                    </div>
                  </motion.button>
                ))}
              </div>
            </motion.div>
          </div>
        </motion.section>
      ) : (
        /* ★ Workspace (라이트 톤 · FigureLabs §6.4) — 채팅 로그 하단 고정 + 인라인 figure */
        <motion.div
          key="workspace"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
          className="flex-1 flex flex-col overflow-hidden bg-surface-alt"
        >
          {/* 채팅 로그 — overflow-y-auto, 자동 스크롤 bottom (최신 하단 고정) */}
          <div className="flex-1 overflow-y-auto px-6 py-8">
            <div className="max-w-3xl mx-auto space-y-4">
              {messages.map((m, mi) => (
                <div key={mi}>
                  {m.blocks.map((b, bi) => {
                    if (b.kind === "text") {
                      return (
                        <ChatMessage
                          key={bi}
                          role={m.role}
                          content={b.text}
                          streaming={streaming && mi === messages.length - 1 &&
                                       bi === m.blocks.length - 1 && m.role === "assistant"}
                        />
                      );
                    }
                    if (b.kind === "figure") {
                      return (
                        <InlineFigure
                          key={bi}
                          title={b.title}
                          caption={b.caption}
                          src={b.src}
                          engine={b.engine}
                          state={b.state}
                        />
                      );
                    }
                    return null;
                  })}
                </div>
              ))}

              {/* 사고 트레이스 카드 — 응답 중 */}
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

/* CRAFT_SPEC §9 — Hero 입력박스 (Surface C · radius 28 · 떠있는 오브젝트) */
function HeroInput({ onSend, disabled }: { onSend: (t: string) => void; disabled: boolean }) {
  const [text, setText] = useState("");
  function go() {
    const t = text.trim();
    if (!t || disabled) return;
    onSend(t);
    setText("");
  }
  return (
    <div className="surface-c rounded-[28px] px-5 py-5
                      shadow-[0_0_0_1px_rgba(255,255,255,.04),0_1px_0_rgba(0,0,0,.25),0_24px_60px_-12px_rgba(0,0,0,.55)]
                      transition-colors duration-200"
         style={{ borderColor: "var(--border)" }}>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            go();
          }
        }}
        rows={2}
        placeholder="Ask a research question…  e.g. Association between UPF intake and MASLD in Korean adults"
        className="hero-textarea w-full bg-transparent outline-none text-white resize-none
                     text-[0.97rem] leading-[1.55] py-1"
        style={{ color: "var(--txt-primary)" }}
      />

      <div className="mt-3 flex items-center gap-2">
        {/* Research⌄ pill */}
        <button className="inline-flex items-center gap-1.5 h-8 px-3 rounded-full text-[0.74rem]
                              transition-colors"
                style={{
                  background: "var(--surface-a)",
                  border: "1px solid var(--border)",
                  color: "var(--txt-secondary)",
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = "var(--hover)"}
                onMouseLeave={(e) => e.currentTarget.style.background = "var(--surface-a)"}>
          Research
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2.5" strokeLinecap="round">
            <path d="M6 9l6 6 6-6" />
          </svg>
        </button>

        {/* 첨부 ico */}
        <button className="w-8 h-8 rounded-full grid place-items-center transition-colors"
                style={{
                  background: "var(--surface-a)",
                  border: "1px solid var(--border)",
                  color: "var(--txt-secondary)",
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = "var(--hover)"}
                onMouseLeave={(e) => e.currentTarget.style.background = "var(--surface-a)"}
                aria-label="첨부">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 10a9 9 0 1 1-18 0V8a4 4 0 0 1 8 0v8a3 3 0 1 1-6 0V10" />
          </svg>
        </button>

        {/* mic ico */}
        <button className="w-8 h-8 rounded-full grid place-items-center transition-colors"
                style={{
                  background: "var(--surface-a)",
                  border: "1px solid var(--border)",
                  color: "var(--txt-secondary)",
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = "var(--hover)"}
                onMouseLeave={(e) => e.currentTarget.style.background = "var(--surface-a)"}
                aria-label="음성">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="9" y="2" width="6" height="12" rx="3" />
            <path d="M5 10v2a7 7 0 0 0 14 0v-2 M12 19v3" />
          </svg>
        </button>

        {/* send (원형, sapphire→cyan 그라데이션) */}
        <button onClick={go} disabled={disabled || !text.trim()}
                className="ml-auto w-9 h-9 rounded-full grid place-items-center text-white
                              transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]
                              disabled:opacity-40"
                style={{
                  background: "linear-gradient(135deg, #2F5EFF, #22D3EE)",
                  boxShadow: "0 4px 14px rgba(47, 94, 255, 0.35)",
                }}
                onMouseEnter={(e) => {
                  if (!disabled && text.trim()) {
                    e.currentTarget.style.transform = "scale(1.06) translateY(-1px)";
                    e.currentTarget.style.boxShadow = "0 6px 20px rgba(47, 94, 255, 0.5)";
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = "scale(1) translateY(0)";
                  e.currentTarget.style.boxShadow = "0 4px 14px rgba(47, 94, 255, 0.35)";
                }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 19V5M5 12l7-7 7 7" />
          </svg>
        </button>
      </div>
    </div>
  );
}
