import type { Metadata } from "next";
import SlimRail from "@/components/SlimRail";
import PreviewPane from "@/components/PreviewPane";

// FRONTEND_NEXTJS_SPEC §6.1: FigureLabs형 2-pane 확정 양식 (2026-06-21 v3).
//   좌 60px slim rail (RECENT 드로어 트리거 + 새 채팅 + 사용자) /
//   가운데 ~40% 채팅 + Composer /
//   우 ~60% 캔버스 (compare ↔ preview 토글).
//
// 사용자 정직 요구: '좌 40% 프롬프트 + 우 60% Before/After + Preview 토글'.
// 이전 240px 사이드바 = 명세 불일치 → SlimRail로 양식 변경.

export const metadata: Metadata = {
  title: "Workspace",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-screen overflow-hidden grid bg-surface-alt
                    grid-cols-1
                    md:grid-cols-[56px_1fr]
                    xl:grid-cols-[56px_minmax(420px,2fr)_minmax(520px,3fr)]">
      <SlimRail />
      <main className="flex flex-col h-screen min-h-0 overflow-hidden border-r border-ink/5 bg-white/60 backdrop-blur-sm">
        {children}
      </main>
      <div className="hidden xl:block h-screen min-h-0 overflow-hidden">
        <PreviewPane />
      </div>
    </div>
  );
}
