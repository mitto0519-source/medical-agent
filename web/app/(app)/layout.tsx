import type { Metadata } from "next";
import RecentSidebar from "@/components/RecentSidebar";
import PreviewPane from "@/components/PreviewPane";

// FRONTEND_NEXTJS_SPEC §2: (app) 그룹 = noindex + CSR. 인증 미들웨어로 게이트.
export const metadata: Metadata = {
  title: "Workspace",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";

// ★ 2026-06-21: placeholder 양식 → 실 컴포넌트로 (사용자 정직 지적 'placeholder 박힌 채 배포 X').
// 좌측 RecentSidebar = /projects API 호출 · 우측 PreviewPane = docx preview.
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-screen grid grid-cols-[260px_1fr_440px] bg-surface-alt">
      <RecentSidebar />
      <main className="flex flex-col overflow-hidden">{children}</main>
      <PreviewPane />
    </div>
  );
}
