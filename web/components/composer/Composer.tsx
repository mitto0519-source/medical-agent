"use client";

import { useRef, useState } from "react";

// UX_CHAT_DESIGN_SPEC §4 + UI_BLUEPRINT R3 (Lovable 컴포저 craft):
//   단일 박스 · 첨부칩 · 모델 pill · @ref 바 · 원형 그라데 send.
//   라이트 워크스페이스 톤에 맞춘 polish (HeroInput과 craft 일관).
type Props = {
  onSend: (msg: string, attachments?: File[]) => void;
  disabled?: boolean;
};

export default function Composer({ onSend, disabled = false }: Props) {
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<File[]>([]);
  const [model, setModel] = useState<"auto" | "haiku" | "sonnet" | "opus">("auto");
  const [refOpen, setRefOpen] = useState(true);
  const fileRef = useRef<HTMLInputElement>(null);

  function send() {
    const t = text.trim();
    if (!t || disabled) return;
    onSend(t, attachments);
    setText("");
    setAttachments([]);
  }

  return (
    <div className="border-t border-ink/5 bg-white/70 backdrop-blur-sm">
      <div className="max-w-3xl mx-auto px-4 py-3.5">
        {/* @ref 바 (R3 — Reuse work / Add reference) */}
        {refOpen && (
          <div className="flex items-center gap-2 mb-2.5 px-3 py-2 rounded-xl
                          bg-surface-alt border border-ink/5 text-[0.72rem] text-ink-subtle">
            <span className="text-ink-muted">@</span>
            <span>다른 프로젝트 작업 재사용</span>
            <button className="ml-auto h-6 px-2.5 rounded-full border border-ink/10 bg-white
                               text-[0.68rem] text-ink hover:border-sapphire/30 transition-colors">
              Add reference
            </button>
            <button onClick={() => setRefOpen(false)} aria-label="닫기"
                    className="text-ink-muted hover:text-ink transition-colors">✕</button>
          </div>
        )}

        {/* 첨부 칩 */}
        {attachments.length > 0 && (
          <div className="flex gap-2 mb-2 flex-wrap">
            {attachments.map((f, i) => (
              <span key={i}
                className="inline-flex items-center gap-1 px-2.5 py-1 bg-sapphire-50 text-sapphire text-xs rounded-full">
                <PaperclipIcon /> {f.name}
                <button onClick={() => setAttachments((a) => a.filter((_, idx) => idx !== i))}
                        className="ml-1 text-ink-muted hover:text-danger" aria-label="remove">×</button>
              </span>
            ))}
          </div>
        )}

        {/* 입력 박스 — rounded surface, craft */}
        <div className="rounded-[18px] border border-ink/10 bg-white px-3.5 pt-3 pb-2.5
                        shadow-[0_1px_2px_rgba(34,34,34,0.03)]
                        focus-within:border-sapphire/40 focus-within:shadow-[0_0_0_3px_rgba(47,94,255,0.08)]
                        transition-all duration-200">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
            }}
            disabled={disabled}
            placeholder="Ask Medical Agent…  (Enter 전송 · Shift+Enter 줄바꿈)"
            rows={1}
            className="w-full resize-none bg-transparent outline-none text-sm leading-6 py-1 max-h-40 text-ink"
          />

          <div className="mt-2 flex items-center gap-2">
            {/* 첨부 */}
            <button onClick={() => fileRef.current?.click()} aria-label="첨부"
                    className="w-8 h-8 rounded-full grid place-items-center text-ink-muted
                               border border-ink/10 hover:bg-surface-alt hover:text-sapphire transition-colors">
              <PaperclipIcon />
            </button>
            <input ref={fileRef} type="file" multiple hidden
              onChange={(e) => {
                const files = Array.from(e.target.files || []);
                setAttachments((a) => [...a, ...files].slice(0, 6));
                if (fileRef.current) fileRef.current.value = "";
              }}
            />

            {/* 모델 pill */}
            <div className="inline-flex items-center h-8 px-3 rounded-full border border-ink/10
                            bg-surface-alt text-[0.74rem] text-ink-subtle">
              <select value={model} onChange={(e) => setModel(e.target.value as typeof model)}
                      className="bg-transparent border-none focus:outline-none cursor-pointer pr-1">
                <option value="auto">⚡ auto</option>
                <option value="haiku">Haiku</option>
                <option value="sonnet">Sonnet</option>
                <option value="opus">Opus</option>
              </select>
            </div>

            {/* mic */}
            <button aria-label="음성"
                    className="w-8 h-8 rounded-full grid place-items-center text-ink-muted
                               border border-ink/10 hover:bg-surface-alt hover:text-sapphire transition-colors">
              <MicIcon />
            </button>

            {/* send (원형, sapphire→cyan) */}
            <button onClick={send} disabled={disabled || !text.trim()}
                    className="ml-auto w-9 h-9 rounded-full grid place-items-center text-white
                               transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] disabled:opacity-40"
                    style={{ background: "linear-gradient(135deg, #2F5EFF, #22D3EE)",
                             boxShadow: "0 4px 14px rgba(47,94,255,0.3)" }}
                    onMouseEnter={(e) => { if (!disabled && text.trim()) e.currentTarget.style.transform = "scale(1.06)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.transform = "scale(1)"; }}>
              {disabled ? <span className="text-xs">···</span> : <ArrowUpIcon />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function PaperclipIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 10a9 9 0 1 1-18 0V8a4 4 0 0 1 8 0v8a3 3 0 1 1-6 0V10" />
    </svg>
  );
}
function MicIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 10v2a7 7 0 0 0 14 0v-2 M12 19v3" />
    </svg>
  );
}
function ArrowUpIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 19V5M5 12l7-7 7 7" />
    </svg>
  );
}
