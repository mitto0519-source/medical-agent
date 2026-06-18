import type { Metadata } from "next";
import "./globals.css";

// FRONTEND_NEXTJS_SPEC §4: Metadata API + 다국어
export const metadata: Metadata = {
  title: {
    default: "Medical-Agent — Vibe Paper Copilot",
    template: "%s · Medical-Agent",
  },
  description:
    "임상 / 번역의학 연구 코파일럿. KYRBS·KNHANES 공중보건 데이터 기반 주제 탐색 → 신규성 확인 → survey-weighted 통계 → IMRaD 작성 보조.",
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "https://medical-agent.app"),
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    locale: "ko_KR",
    siteName: "Medical-Agent",
  },
  robots: {
    index: true, // (public) 그룹에서만 활성. (app)는 layout에서 noindex 덮어씀.
    follow: true,
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="font-sans antialiased bg-surface-alt text-ink min-h-screen">
        {children}
      </body>
    </html>
  );
}
