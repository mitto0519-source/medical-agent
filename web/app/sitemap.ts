import type { MetadataRoute } from "next";

// FRONTEND_NEXTJS_SPEC §4 / §13. 공개 라우트만 — (app) 금지.
export default function sitemap(): MetadataRoute.Sitemap {
  const base = process.env.NEXT_PUBLIC_SITE_URL || "https://medical-agent.app";
  return [
    { url: `${base}/`, lastModified: new Date(), changeFrequency: "weekly", priority: 1.0 },
    { url: `${base}/methods`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.7 },
    // research/concept 페이지는 백엔드에서 동적 수집 — Phase 3 다음 사이클.
  ];
}
