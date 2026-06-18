import type { Metadata } from "next";
import { notFound } from "next/navigation";

// FRONTEND_NEXTJS_SPEC §3 + §5.2: ISR + MedicalCondition JSON-LD (MeSH/UMLS).
export const revalidate = 7776000; // 3개월

type Concept = {
  cui: string;
  label: string;
  domain: string;
  definition: string;
  mesh?: string;
  umls?: string;
  relatedPapers: { pmid: string; title: string; year: number }[];
};

async function fetchConcept(cui: string): Promise<Concept | null> {
  // Phase 3 골격 — 다음 사이클에 FastAPI /concept/{cui} 또는 graph.json 직접 read.
  const stub: Record<string, Concept> = {
    "D000094263": {
      cui: "D000094263",
      label: "Metabolic dysfunction-associated steatotic liver disease (MASLD)",
      domain: "Hepatology",
      definition:
        "지방간 + 대사이상(비만/당뇨/이상지질혈증/고혈압 중 하나) 기반 신규 명명. 2023년 다국제 학회 합의에서 NAFLD를 대체.",
      mesh: "D000094263",
      relatedPapers: [
        { pmid: "38542705", title: "Multi-society Delphi consensus on MASLD nomenclature", year: 2024 },
      ],
    },
    "C_adolescent": {
      cui: "C_adolescent",
      label: "Adolescent (청소년)",
      domain: "Population",
      definition:
        "13~19세. KYRBS(청소년건강행태조사) 표준 대상 인구. survey-weighted 분석 기본.",
      mesh: "D000293",
      relatedPapers: [],
    },
  };
  return stub[cui] || null;
}

export async function generateMetadata({ params }: { params: Promise<{ cui: string }> }): Promise<Metadata> {
  const { cui } = await params;
  const c = await fetchConcept(cui);
  if (!c) return { title: "Concept not found" };
  return {
    title: c.label,
    description: c.definition.slice(0, 160),
    alternates: { canonical: `/concept/${cui}` },
  };
}

export default async function ConceptPage({ params }: { params: Promise<{ cui: string }> }) {
  const { cui } = await params;
  const c = await fetchConcept(cui);
  if (!c) notFound();

  // ★ MedicalCondition + MedicalCode (MeSH) JSON-LD
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "MedicalCondition",
    name: c.label,
    description: c.definition,
    code: c.mesh
      ? { "@type": "MedicalCode", codingSystem: "MeSH", codeValue: c.mesh }
      : undefined,
    sameAs: c.umls ? [`https://uts.nlm.nih.gov/uts/umls/concept/${c.umls}`] : undefined,
  };

  return (
    <main className="max-w-3xl mx-auto px-6 py-10">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />

      <header className="mb-6">
        <div className="text-xs text-ink-muted uppercase tracking-wide">Medical Concept · {c.domain}</div>
        <h1 className="text-3xl font-semibold mt-2 tracking-tight">{c.label}</h1>
        {c.mesh && (
          <div className="text-sm text-ink-subtle mt-1">
            MeSH: <code className="font-mono">{c.mesh}</code>
          </div>
        )}
      </header>

      <section className="card mb-6">
        <h2 className="text-sm font-semibold uppercase text-ink-subtle mb-2">정의</h2>
        <p>{c.definition}</p>
      </section>

      {c.relatedPapers.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold mb-3">관련 문헌 ({c.relatedPapers.length})</h2>
          <ul className="space-y-2">
            {c.relatedPapers.map((p) => (
              <li key={p.pmid} className="card">
                <a
                  href={`https://pubmed.ncbi.nlm.nih.gov/${p.pmid}/`}
                  target="_blank"
                  rel="noopener"
                  className="text-sapphire"
                >
                  {p.title}
                </a>
                <span className="text-xs text-ink-muted ml-2">({p.year}) PMID:{p.pmid}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
