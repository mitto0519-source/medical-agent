"use client";

// FRONTEND_NEXTJS_SPEC §6.2: preview 모드 — 풀버전 reading view.
// 톤: white paper (A4, serif). 앱 chrome (sapphire glass)와 의도적 대비.
// DESIGN-LANGUAGE §6 타이포 위계 + §7 정보 피라미드.

type SectionMap = Record<string, { current: string; revised?: string }>;

const ORDER = [
  "Abstract", "Introduction", "Methods", "Results",
  "Discussion", "Conclusion", "Tables", "References",
];

export default function FullPaperPreview({ sections }: { sections: SectionMap }) {
  const filled = ORDER.filter((s) => (sections[s]?.current || "").trim().length > 0);
  const empty = filled.length === 0;

  return (
    <div className="min-h-full py-10 px-6 flex justify-center">
      {/* A4 페이지 — DESIGN.md figure 톤 차용 (serif, double-space) */}
      <article
        className="bg-white w-full max-w-[820px]
                     shadow-[0_2px_4px_rgba(34,34,34,0.04),0_20px_48px_rgba(34,34,34,0.08)]
                     border border-ink/5
                     rounded-[2px]
                     px-16 py-14
                     font-serif text-ink"
        style={{
          fontFamily:
            '"Source Serif Pro", "Noto Serif KR", "Times New Roman", Georgia, serif',
          lineHeight: 1.75,
        }}
      >
        {/* 타이틀 — 사용자 프로젝트명 자리 */}
        <header className="border-b border-ink/10 pb-6 mb-8">
          <div className="text-[0.65rem] tracking-[0.2em] uppercase text-ink-muted mb-2">
            Manuscript Preview
          </div>
          <h1
            className="text-2xl font-semibold leading-tight tracking-tight text-ink"
            style={{ fontFamily: "inherit" }}
          >
            (제목 없음)
          </h1>
          <p className="mt-2 text-xs text-ink-muted italic">
            채팅에서 작성 중인 본문이 여기에 자동으로 조립됩니다.
          </p>
        </header>

        {/* 빈 상태 */}
        {empty && (
          <div className="py-16 text-center">
            <div className="inline-block text-4xl text-ink/10 mb-4">¶</div>
            <div className="text-sm text-ink-subtle">아직 채워진 섹션이 없습니다.</div>
            <div className="mt-1 text-xs text-ink-muted">
              좌측 채팅에서 분석을 요청하세요.
            </div>
          </div>
        )}

        {/* 섹션들 */}
        {!empty &&
          filled.map((s) => (
            <section key={s} className="mb-10">
              <h2 className="text-[1.05rem] font-semibold tracking-tight mb-3
                              before:content-[''] before:block before:w-8 before:h-px
                              before:bg-sapphire/40 before:mb-2">
                {s}
              </h2>
              <div className="text-[0.95rem] whitespace-pre-wrap"
                   style={{ fontFamily: "inherit", textIndent: "1.5em" }}>
                {sections[s]?.current}
              </div>
            </section>
          ))}

        {/* 푸터 — 미리보기임을 알리는 워터마크 */}
        <footer className="mt-12 pt-6 border-t border-ink/10 flex items-center justify-between text-[0.65rem] text-ink-muted">
          <span className="tracking-[0.15em] uppercase">Medical-Agent · Reading View</span>
          <span className="tabular-nums">{filled.length} / {ORDER.length} sections</span>
        </footer>
      </article>
    </div>
  );
}
