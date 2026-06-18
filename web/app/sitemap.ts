import type { MetadataRoute } from "next";

// FRONTEND_NEXTJS_SPEC §4: 사이트맵 — FastAPI /sitemap-data 에서 동적 수집.
// 공개 라우트만 (app) 금지. AI 크롤러가 모든 research/concept 페이지 찾을 수 있게.
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = process.env.NEXT_PUBLIC_SITE_URL || "https://medical-agent.app";
  const apiBase = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

  const staticEntries: MetadataRoute.Sitemap = [
    { url: `${base}/`, lastModified: new Date(), changeFrequency: "weekly", priority: 1.0 },
    { url: `${base}/methods`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.7 },
  ];

  // 동적 수집 — paper PMIDs + concept CUIs (graph.json)
  try {
    const res = await fetch(`${apiBase}/sitemap-data`, { next: { revalidate: 86400 } });
    if (res.ok) {
      const d: { papers?: string[]; concepts?: string[] } = await res.json();
      const now = new Date();
      for (const pmid of (d.papers || []).slice(0, 10000)) {
        staticEntries.push({
          url: `${base}/research/${pmid}`,
          lastModified: now,
          changeFrequency: "monthly",
          priority: 0.6,
        });
      }
      for (const cui of (d.concepts || []).slice(0, 2000)) {
        staticEntries.push({
          url: `${base}/concept/${cui}`,
          lastModified: now,
          changeFrequency: "monthly",
          priority: 0.5,
        });
      }
    }
  } catch {
    // FastAPI 미가동 시 정적 entries만 (안전 fallback)
  }
  return staticEntries;
}
