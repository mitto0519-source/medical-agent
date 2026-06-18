import type { Metadata } from "next";
import { notFound } from "next/navigation";

// FRONTEND_NEXTJS_SPEC §3 + §5.2 — ISR + ScholarlyArticle/MedicalWebPage JSON-LD.
export const revalidate = 7776000; // 3개월 (GEO freshness)

type ResearchTopic = {
  slug: string;
  title: string;
  abstract: string;
  publishedDate: string;
  modifiedDate: string;
  authors: { name: string; affiliation?: string }[];
  citations: { pmid: string; title: string; journal?: string; year?: number }[];
  meshTopics: { code: string; label: string }[];
};

async function fetchTopic(slug: string): Promise<ResearchTopic | null> {
  // Phase 3 골격 — 다음 사이클: FastAPI /research/{slug} 호출.
  // 지금은 정적 시드(MASLD 예시) 한 건만 반환.
  if (slug === "masld-classification") {
    return {
      slug,
      title: "MASLD vs MetALD vs NAFLD — 2026 명명 체계 변화",
      abstract:
        "다국제 학회 합의로 도입된 MASLD(Metabolic dysfunction-associated steatotic liver disease) 정의가 임상 진단·역학 분석·신약 시험 설계에 미치는 영향. NAFLD 진단 기준 차이, FLI/HSI 지표의 검증 양식, MetALD 중간 카테고리 적용.",
      publishedDate: "2026-04-01",
      modifiedDate: "2026-06-15",
      authors: [{ name: "Medical-Agent Research Team" }],
      citations: [
        { pmid: "38542705", title: "Multi-society Delphi consensus on MASLD nomenclature", journal: "Hepatology", year: 2024 },
      ],
      meshTopics: [
        { code: "D000094263", label: "Metabolic dysfunction-associated steatotic liver disease" },
        { code: "D065626", label: "Non-alcoholic Fatty Liver Disease" },
      ],
    };
  }
  return null;
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const topic = await fetchTopic(slug);
  if (!topic) return { title: "Topic not found" };
  return {
    title: topic.title,
    description: topic.abstract.slice(0, 160),
    alternates: { canonical: `/research/${slug}` },
    openGraph: {
      title: topic.title,
      description: topic.abstract.slice(0, 200),
      type: "article",
      publishedTime: topic.publishedDate,
      modifiedTime: topic.modifiedDate,
    },
  };
}

export default async function ResearchTopicPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const topic = await fetchTopic(slug);
  if (!topic) notFound();

  // ★ JSON-LD ScholarlyArticle + MedicalWebPage — GEO E-E-A-T signals
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": ["ScholarlyArticle", "MedicalWebPage"],
    headline: topic.title,
    abstract: topic.abstract,
    datePublished: topic.publishedDate,
    dateModified: topic.modifiedDate,
    author: topic.authors.map((a) => ({ "@type": "Person", name: a.name, affiliation: a.affiliation })),
    citation: topic.citations.map((c) => ({
      "@type": "ScholarlyArticle",
      identifier: `PMID:${c.pmid}`,
      name: c.title,
      isPartOf: c.journal ? { "@type": "Periodical", name: c.journal } : undefined,
      datePublished: c.year?.toString(),
    })),
    about: topic.meshTopics.map((m) => ({
      "@type": "MedicalCondition",
      code: { "@type": "MedicalCode", codingSystem: "MeSH", codeValue: m.code },
      name: m.label,
    })),
  };

  return (
    <main className="max-w-3xl mx-auto px-6 py-10">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />

      <article>
        <header className="mb-6">
          <div className="text-xs text-ink-muted uppercase tracking-wide">Research Explainer</div>
          <h1 className="text-3xl font-semibold mt-2 mb-3 tracking-tight">{topic.title}</h1>
          <time className="text-sm text-ink-subtle" dateTime={topic.modifiedDate}>
            업데이트: {topic.modifiedDate}
          </time>
        </header>

        <section className="card mb-6">
          <h2 className="text-sm font-semibold uppercase text-ink-subtle mb-2">결론 먼저</h2>
          <p className="text-ink">{topic.abstract}</p>
        </section>

        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-3">관련 MeSH 개념</h2>
          <ul className="flex flex-wrap gap-2">
            {topic.meshTopics.map((m) => (
              <li key={m.code}>
                <a
                  href={`/concept/${m.code}`}
                  className="px-3 py-1 text-sm bg-sapphire-50 text-sapphire rounded-md"
                >
                  {m.label}
                </a>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold mb-3">인용 ({topic.citations.length})</h2>
          <ul className="space-y-2">
            {topic.citations.map((c) => (
              <li key={c.pmid} className="card">
                <cite className="not-italic">
                  <a
                    href={`https://pubmed.ncbi.nlm.nih.gov/${c.pmid}/`}
                    target="_blank"
                    rel="noopener"
                    className="text-sapphire underline"
                  >
                    {c.title}
                  </a>
                </cite>
                {c.journal && <span className="text-ink-subtle text-sm"> · {c.journal} ({c.year})</span>}
                <span className="text-xs text-ink-muted ml-2">PMID:{c.pmid}</span>
              </li>
            ))}
          </ul>
        </section>
      </article>
    </main>
  );
}
