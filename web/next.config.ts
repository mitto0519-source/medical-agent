import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000",
    // ★ NEXT_PUBLIC_SITE_URL은 Vercel 배포 후 자동 결정되는 도메인 (vercel env로 설정).
    //   placeholder 'medical-agent.vercel.app' 사용 X (다른 사용자 차지).
    NEXT_PUBLIC_SITE_URL: process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000",
  },
  // ★ 2026-06-20 v6: HF Space 단일 컨테이너 — /fastapi/* → FastAPI:8000 proxy.
  // 브라우저는 같은 도메인 /fastapi 호출, Next.js 서버가 localhost:8000으로 rewrite.
  // 짝: NEXT_PUBLIC_API_BASE="/fastapi" (Dockerfile env + supervisord.conf).
  async rewrites() {
    return [
      {
        source: "/fastapi/:path*",
        destination: "http://localhost:8000/:path*",
      },
    ];
  },
  // FRONTEND_NEXTJS_SPEC §4: AI 크롤러 허용 (GEO 전제). robots는 (public)만 색인.
  experimental: {
    optimizePackageImports: ["@tanstack/react-query"],
  },
};

export default config;
