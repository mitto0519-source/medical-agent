import type { Metadata } from "next";

// FRONTEND_NEXTJS_SPEC §2: (app) 그룹 = noindex + CSR. 인증 미들웨어로 게이트.
export const metadata: Metadata = {
  title: "Workspace",
  robots: { index: false, follow: false }, // 워크스페이스는 절대 색인 안 됨
};

export const dynamic = "force-dynamic"; // CSR + SSE — 정적 렌더 금지

export default function AppLayout({ children }: { children: React.ReactNode }) {
  // ★ 3-pane (FRONTEND_NEXTJS_SPEC §6): 좌 RECENT / 중 Chat 하단고정 / 우 TipTap preview.
  // Phase 3 골격 — 실제 구현은 다음 사이클.
  return (
    <div className="h-screen grid grid-cols-[240px_1fr_440px] bg-surface-alt">
      <aside className="border-r border-ink-muted/15 bg-white">
        {/* Sidebar: 프로젝트 목록 + 새 채팅 (가운데에 X — 사용자 요구 명시) */}
        <div className="p-4 border-b border-ink-muted/15">
          <button className="w-full px-3 py-2 bg-sapphire text-white rounded-md text-sm font-medium">
            + 새 채팅
          </button>
        </div>
        <div className="p-3 text-xs text-ink-muted uppercase tracking-wide">RECENT</div>
        {/* /projects API 호출은 다음 사이클 */}
      </aside>

      <main className="flex flex-col overflow-hidden">
        {/* Chat pane — flex-col-reverse 양식으로 하단고정 (UX_CHAT_DESIGN) */}
        {children}
      </main>

      <aside className="border-l border-ink-muted/15 bg-white">
        {/* Preview pane — TipTap manuscript + stat/figures/refs 탭 */}
        <div className="p-4 border-b border-ink-muted/15 text-sm font-medium">
          📄 우측 라이브 프리뷰
        </div>
        <div className="p-4 text-sm text-ink-subtle">
          (Phase 3 다음 사이클 — TipTap manuscript + DockPanels)
        </div>
      </aside>
    </div>
  );
}
