import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "방법론 — Survey-weighted analysis, STROBE, Novelty",
  description:
    "KYRBS·KNHANES 표본 가중 분석, STROBE 체크리스트, novelty checker. Medical-Agent가 환각 통계를 차단하는 양식.",
};

export default function MethodsPage() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": ["Article", "HowTo"],
    headline: "Survey-weighted analysis · STROBE · Novelty",
    description: "Methodology pages explaining how Medical-Agent produces hallucination-free statistics and citations.",
  };
  return (
    <main className="max-w-3xl mx-auto px-6 py-10">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <h1 className="text-3xl font-semibold mb-6">방법론</h1>

      <section className="card mb-4">
        <h2 className="text-lg font-semibold mb-2">★ Survey-weighted regression</h2>
        <p className="text-ink">
          KYRBS·KNHANES는 복합 표본 설계 — 단순 logistic은 표본 가중·층화·집락을 무시해 표준오차 과소추정.
          <strong> survey-weighted (`statsmodels.discrete_model.Logit` w/ `glm.formula`) 사용</strong> →
          aOR / 95% CI / p값이 인구 일반화 가능.
        </p>
      </section>

      <section className="card mb-4">
        <h2 className="text-lg font-semibold mb-2">STROBE 보고 체크리스트</h2>
        <p>22개 항목 자동 점검: 연구 설계 / 대상 / 변수 / 통계 가정 / 한계점. 미통과 시 인라인 warning.</p>
      </section>

      <section className="card mb-4">
        <h2 className="text-lg font-semibold mb-2">Novelty checker (★ 환각 차단)</h2>
        <p>
          본문에 박힌 모든 [PMID:xxx]는 graph.json + RAG hit에 실재해야 함. 미확인 시 BLOCK.
          모든 수치는 stat_result에 추적 가능해야 함 (provenance_id 핀).
        </p>
      </section>
    </main>
  );
}
