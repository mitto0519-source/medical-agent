"use client";

// 채팅 중간에 인라인 Figure 카드 (사용자 정직 '중간중간 그림 인라인').
// 의료 figure는 diffusion X — 실데이터 엔진 렌더(matplotlib/lifelines)만.
// state: "loading" (점격자 + shimmer) → "ready" (figure + 캡션 + 액션)

type FigureProps = {
  title?: string;
  caption?: string;
  src?: string;          // 완성 figure URL (PNG/SVG)
  engine?: string;        // "lifelines · vector"
  state: "loading" | "ready" | "error";
  onInsert?: () => void;
  onDownloadSVG?: () => void;
  onDownloadPNG?: () => void;
  onRegenerate?: () => void;
};

export default function InlineFigure({
  title, caption, src, engine, state,
  onInsert, onDownloadSVG, onDownloadPNG, onRegenerate,
}: FigureProps) {
  return (
    <div className="anim-slide-in my-3">
      <div className="rounded-2xl bg-white border border-ink/5
                        shadow-[0_1px_2px_rgba(34,34,34,0.04),0_8px_24px_rgba(34,34,34,0.04)]
                        overflow-hidden">
        {/* 헤더 — 제목 + 엔진 배지 */}
        <div className="px-4 py-3 flex items-center gap-2 border-b border-ink/5">
          <span className="text-base">📈</span>
          <span className="text-[0.85rem] font-medium text-ink">
            {title || "Figure"}
          </span>
          {engine && (
            <span className="ml-auto text-[0.65rem] tracking-[0.1em] uppercase
                              px-2 py-0.5 rounded-full bg-sapphire/8 text-sapphire">
              engine: {engine}
            </span>
          )}
        </div>

        {/* 본문 — loading / ready / error */}
        <div className="relative bg-[#fafaf7]">
          {state === "loading" && (
            <div className="h-64 flex flex-col items-center justify-center gap-3 p-6">
              {/* 점격자 — Lovable 양식 */}
              <div className="grid grid-cols-12 gap-1.5 opacity-50">
                {Array.from({ length: 48 }).map((_, i) => (
                  <div key={i}
                       className="w-1 h-1 rounded-full bg-ink/15 figure-shimmer"
                       style={{
                         animationDelay: `${(i % 12) * 0.06}s`,
                       }} />
                ))}
              </div>
              <div className="text-[0.78rem] text-ink-muted">
                Figure 생성 중 · 실데이터로 렌더
              </div>
            </div>
          )}

          {state === "ready" && src && (
            <a href={src} target="_blank" rel="noreferrer" className="block">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={src} alt={title || "Figure"} className="w-full h-auto block" />
            </a>
          )}

          {state === "error" && (
            <div className="h-32 flex items-center justify-center px-6">
              <div className="text-center">
                <div className="text-sm text-danger mb-1">생성 실패</div>
                <button onClick={onRegenerate}
                        className="text-xs text-sapphire hover:underline">
                  재시도
                </button>
              </div>
            </div>
          )}
        </div>

        {/* 캡션 + 액션 */}
        {(caption || state === "ready") && (
          <div className="px-4 py-3 border-t border-ink/5 bg-white">
            {caption && (
              <p className="text-[0.78rem] text-ink-subtle leading-relaxed mb-3">
                {caption}
              </p>
            )}
            {state === "ready" && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <ChipBtn onClick={onInsert} primary>
                  <PathArrow /> 논문에 삽입
                </ChipBtn>
                <ChipBtn onClick={onDownloadSVG}>
                  SVG
                </ChipBtn>
                <ChipBtn onClick={onDownloadPNG}>
                  PNG 300dpi
                </ChipBtn>
                <ChipBtn onClick={onRegenerate}>
                  재생성
                </ChipBtn>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ChipBtn({
  children, onClick, primary,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  primary?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={
        "inline-flex items-center gap-1.5 px-3 h-7 rounded-full text-[0.72rem] font-medium " +
        "transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] " +
        (primary
          ? "bg-sapphire text-white shadow-[0_2px_8px_rgba(31,78,121,0.18)] hover:-translate-y-0.5 hover:shadow-[0_4px_14px_rgba(31,78,121,0.28)]"
          : "bg-ink/5 text-ink-subtle hover:bg-ink/8 hover:text-ink")
      }
    >
      {children}
    </button>
  );
}

function PathArrow() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2.5" strokeLinecap="round">
      <path d="M5 12h14M13 5l7 7-7 7" />
    </svg>
  );
}
