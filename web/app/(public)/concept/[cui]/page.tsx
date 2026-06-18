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
  // FastAPI GET /concept/{cui} — medical_ontology + graph.json fallback (RSC).
  const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
  try {
    const res = await fetch(`${base}/concept/${encodeURIComponent(cui)}`, {
      next: { revalidate: 7776000 },
    });
    if (!res.ok) return null;
    const d = await res.json();
    return {
      cui: d.cui,
      label: d.label || cui,
      domain: d.domain || "Medical Concept",
      definition: d.definition || (d.keywords?.length ? `Keywords: ${d.keywords.join(", ")}` : ""),
      mesh: d.mesh,
      umls: d.umls,
      relatedPapers: [],
    };
  } catch {
    return null;
  }
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
