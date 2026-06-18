import type { MetadataRoute } from "next";

// FRONTEND_NEXTJS_SPEC §4: AI 크롤러 허용 (GEO 전제). (app)는 noindex.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      // 공개 콘텐츠 — 모든 크롤러 허용
      { userAgent: "*", allow: "/", disallow: ["/app/", "/api/"] },
      // AI 크롤러 명시 허용 (GEO)
      { userAgent: "GPTBot", allow: "/", disallow: ["/app/"] },
      { userAgent: "ClaudeBot", allow: "/", disallow: ["/app/"] },
      { userAgent: "PerplexityBot", allow: "/", disallow: ["/app/"] },
      { userAgent: "Google-Extended", allow: "/", disallow: ["/app/"] },
      { userAgent: "Applebot-Extended", allow: "/", disallow: ["/app/"] },
    ],
    sitemap: `${process.env.NEXT_PUBLIC_SITE_URL || "https://medical-agent.app"}/sitemap.xml`,
  };
}
