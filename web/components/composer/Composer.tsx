"use client";

import { useRef, useState } from "react";

// UX_CHAT_DESIGN_SPEC §4: 단일 박스 컴포저 — 첨부칩·모델·@ref·슬래시메뉴 내장.
type Props = {
  onSend: (msg: string, attachments?: File[]) => void;
  disabled?: boolean;
};

export default function Composer({ onSend, disabled = false }: Props) {
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<File[]>([]);
  const [model, setModel] = useState<"auto" | "haiku" | "sonnet" | "opus">("auto");
  const fileRef = useRef<HTMLInputElement>(null);

  function send() {
    const t = text.trim();
    if (!t || disabled) return;
    onSend(t, attachments);
    setText("");
    setAttachments([]);
  }

  return (
    <div className="border-t border-ink-muted/15 bg-white">
      <div className="max-w-3xl mx-auto p-3">
        {attachments.length > 0 && (
          <div className="flex gap-2 mb-2 flex-wrap">
            {attachments.map((f, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 px-2 py-1 bg-sapphire-50 text-sapphire text-xs rounded"
              >
                📎 {f.name}
                <button
                  onClick={() => setAttachments((a) => a.filter((_, idx) => idx !== i))}
                  className="ml-1 text-ink-muted hover:text-danger"
                  aria-label="remove"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}

        <div className="flex items-end gap-2 border border-ink-muted/20 rounded-lg px-3 py-2 focus-within:border-sapphire">
          {/* 첨부 트리거 */}
          <button
            onClick={() => fileRef.current?.click()}
            className="text-ink-muted hover:text-sapphire"
            aria-label="첨부"
          >
            📎
          </button>
          <input
            ref={fileRef}
            type="file"
            multiple
            hidden
            onChange={(e) => {
              const files = Array.from(e.target.files || []);
              setAttachments((a) => [...a, ...files].slice(0, 6));
              if (fileRef.current) fileRef.current.value = "";
            }}
          />

          {/* 모델 선택 */}
          <select
            value={model}
            onChange={(e) => setModel(e.target.value as typeof model)}
            className="text-xs bg-transparent border-none text-ink-subtle focus:outline-none cursor-pointer"
          >
            <option value="auto">⚡ auto</option>
            <option value="haiku">Haiku</option>
            <option value="sonnet">Sonnet</option>
            <option value="opus">Opus</option>
          </select>

          {/* 입력 */}
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            disabled={disabled}
            placeholder="MASLD vs MetALD 정의를 비교하고 싶어… (Enter 전송 · Shift+Enter 줄바꿈)"
            rows={1}
            className="flex-1 resize-none bg-transparent outline-none text-sm py-1.5 max-h-32"
          />

          {/* 전송 */}
          <button
            onClick={send}
            disabled={disabled || !text.trim()}
            className="px-3 py-1.5 bg-sapphire text-white rounded-md text-sm font-medium disabled:opacity-40"
          >
            {disabled ? "..." : "↑"}
          </button>
        </div>
      </div>
    </div>
  );
}
