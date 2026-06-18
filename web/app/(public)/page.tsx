import type { Metadata } from "next";

// FRONTEND_NEXTJS_SPEC §3: SSG 랜딩 + JSON-LD (GEO E-E-A-T 신호).
export const metadata: Metadata = {
  title: "Medical-Agent — Vibe Paper Copilot for Clinical Research",
  description:
    "임상 / 번역의학 연구 코파일럿. 한 명의 매우 똑똑한 연구 비서처럼 — 주제 → 신규성 → survey-weighted 통계 → IMRaD 작성.",
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: "Medical-Agent",
  description:
    "Clinical/translational research copilot grounded in survey-weighted statistics, PubMed evidence, and reproducible provenance.",
  url: "https://medical-agent.app",
  publisher: { "@type": "Organization", name: "Medical-Agent" },
};

export default function LandingPage() {
  return (
    <main className="min-h-screen flex flex-col">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <header className="border-b border-ink-muted/15 bg-white">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="font-semibold text-lg text-sapphire">Medical-Agent</div>
          <nav className="flex gap-6 text-sm text-ink-subtle">
            <a href="/research">Research</a>
            <a href="/concept">Concepts</a>
            <a href="/methods">Methods</a>
            <a href="/app" className="text-sapphire font-medium">앱 열기 →</a>
          </nav>
        </div>
      </header>

      <section className="flex-1 max-w-4xl mx-auto px-6 py-20">
        <h1 className="text-4xl font-semibold tracking-tight text-ink mb-4">
          한 명의 매우 똑똑한 연구 비서.
        </h1>
        <p className="text-lg text-ink-subtle mb-8">
          KYRBS·KNHANES 공중보건 데이터로 주제 탐색 → 신규성 확인 → survey-weighted 통계 → IMRaD 초안.
          숫자 먼저, 산문 나중 — 환각 통계는 구조적으로 차단합니다.
        </p>
        <div className="flex gap-4">
          <a href="/app" className="px-5 py-2.5 bg-sapphire text-white rounded-md font-medium shadow-glass">
            새 연구 시작
          </a>
          <a href="/methods" className="px-5 py-2.5 border border-ink-muted/20 rounded-md text-ink">
            방법론 보기
          </a>
        </div>

        <div className="grid grid-cols-3 gap-4 mt-16">
          <div className="card">
            <div className="text-sm text-ink-muted">근거 그래프</div>
            <div className="stat-number text-sapphire">10,141<span className="stat-unit"> nodes</span></div>
          </div>
          <div className="card">
            <div className="text-sm text-ink-muted">PubMed 인덱스</div>
            <div className="stat-number text-sapphire">75K+<span className="stat-unit"> chunks</span></div>
          </div>
          <div className="card">
            <div className="text-sm text-ink-muted">검증 게이트</div>
            <div className="stat-number text-sapphire">★ 숫자 먼저</div>
          </div>
        </div>
      </section>

      <footer className="border-t border-ink-muted/15 bg-white">
        <div className="max-w-6xl mx-auto px-6 py-4 text-sm text-ink-muted flex justify-between">
          <span>© Medical-Agent</span>
          <span>YMYL · E-E-A-T compliant</span>
        </div>
      </footer>
    </main>
  );
}
