import type { Metadata } from "next";
import RecentSidebar from "@/components/RecentSidebar";
import PreviewPane from "@/components/PreviewPane";

// FRONTEND_NEXTJS_SPEC §2: (app) 그룹 = noindex + CSR. 인증 미들웨어로 게이트.
export const metadata: Metadata = {
  title: "Workspace",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";

// ★ 2026-06-21: 반응형 3-pane (사용자 정직: '비율 안 맞음').
//   · 모바일(<768px): 채팅만
//   · 태블릿(>=768px): 좌 사이드바 + 채팅
//   · 데스크탑(>=1280px): 3-pane (좌 + 채팅 + 우)
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-screen grid bg-surface-alt
                    grid-cols-1
                    md:grid-cols-[240px_1fr]
                    xl:grid-cols-[260px_1fr_440px]">
      <div className="hidden md:block">
        <RecentSidebar />
      </div>
      <main className="flex flex-col overflow-hidden">{children}</main>
      <div className="hidden xl:block">
        <PreviewPane />
      </div>
    </div>
  );
}
