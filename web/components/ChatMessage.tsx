"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";

// 채팅 메시지 — Lovable 채팅 craft 양식 적용.
// 이미지/표/코드/인용/리스트 인라인 렌더 (사용자 요구: '그림도 로그도 다 보여줘야해').

type Props = {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  onReply?: () => void;
  onUp?: () => void;
  onDown?: () => void;
  onCopy?: () => void;
};

export default function ChatMessage({
  role, content, streaming, onReply, onUp, onDown, onCopy,
}: Props) {
  if (role === "user") {
    return (
      <div className="anim-slide-in flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-tr-md bg-sapphire text-white px-4 py-3
                          text-[0.92rem] leading-[1.6] whitespace-pre-wrap
                          shadow-[0_2px_8px_rgba(31,78,121,0.18)]">
          {content}
        </div>
      </div>
    );
  }

  return (
    <div className="anim-slide-in flex justify-start">
      <div className="max-w-[88%] group">
        {/* 본문 카드 — Lovable 양식 흰 카드 + 미세 그림자 */}
        <div className="rounded-2xl rounded-tl-md bg-white border border-ink/5 px-5 py-4
                          shadow-[0_1px_2px_rgba(34,34,34,0.04),0_8px_24px_rgba(34,34,34,0.04)]">
          <div className="chat-md text-[0.93rem] text-ink">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeRaw]}
              components={{
                // 이미지 — 클릭 시 새 창 열림 (확대)
                img: ({ src, alt }) => {
                  const url = typeof src === "string" ? src : "";
                  return (
                    <a href={url} target="_blank" rel="noreferrer" className="block">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={url} alt={alt || ""} loading="lazy" />
                    </a>
                  );
                },
                // 외부 링크 — 새 창
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noreferrer">
                    {children}
                  </a>
                ),
              }}
            >
              {content || ""}
            </ReactMarkdown>
            {streaming && <span className="stream-cursor" />}
          </div>
        </div>

        {/* 메시지 액션 행 (Lovable 양식: ↩👍👎⧉⋯) — hover 시 등장 */}
        {!streaming && (
          <div className="flex items-center gap-0.5 mt-1.5 pl-1
                            opacity-0 group-hover:opacity-100 transition-opacity duration-200">
            <ActionBtn label="다시" onClick={onReply}>
              <path d="M3 7l4-4 4 4M3 7v6a4 4 0 0 0 4 4h10" />
            </ActionBtn>
            <ActionBtn label="좋아요" onClick={onUp}>
              <path d="M7 10v10h10l3-7-2-3h-5l1-4a2 2 0 0 0-2-2L9 9l-2 1z" />
            </ActionBtn>
            <ActionBtn label="별로" onClick={onDown}>
              <path d="M17 14V4H7L4 11l2 3h5l-1 4a2 2 0 0 0 2 2l3-5 2-1z" />
            </ActionBtn>
            <ActionBtn label="복사" onClick={() => {
              navigator.clipboard?.writeText(content);
              onCopy?.();
            }}>
              <rect x="9" y="9" width="11" height="11" rx="2" />
              <path d="M5 15V5a2 2 0 0 1 2-2h10" />
            </ActionBtn>
          </div>
        )}
      </div>
    </div>
  );
}

function ActionBtn({
  label, onClick, children,
}: {
  label: string;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className="w-7 h-7 rounded-md flex items-center justify-center
                    text-ink-muted hover:text-ink hover:bg-ink/5
                    transition-colors duration-150"
    >
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        {children}
      </svg>
    </button>
  );
}
