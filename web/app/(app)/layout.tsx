import type { Metadata } from "next";
import RecentSidebar from "@/components/RecentSidebar";
import PreviewPane from "@/components/PreviewPane";

// FRONTEND_NEXTJS_SPEC §2: (app) 그룹 = noindex + CSR. 인증 미들웨어로 게이트.
export const metadata: Metadata = {
  title: "Workspace",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";

// ★ 2026-06-21: 반응형 3-pane + 높이 고정 (사용자 정직: 'Composer가 밑으로 밀려남').
//   · h-screen on root + min-h-0 on grid items = 자식이 부모 밀어내는 거 차단
//   · 각 컬럼 = h-screen overflow-hidden (각자 스크롤)
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-screen overflow-hidden grid bg-surface-alt
                    grid-cols-1
                    md:grid-cols-[240px_1fr]
                    xl:grid-cols-[260px_1fr_440px]">
      <div className="hidden md:block h-screen min-h-0 overflow-hidden">
        <RecentSidebar />
      </div>
      <main className="flex flex-col h-screen min-h-0 overflow-hidden">{children}</main>
      <div className="hidden xl:block h-screen min-h-0 overflow-hidden">
        <PreviewPane />
      </div>
    </div>
  );
}
