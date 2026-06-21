"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import BeforeAfter from "./BeforeAfter";
import FullPaperPreview from "./FullPaperPreview";

// FRONTEND_NEXTJS_SPEC §6.1~6.4: FigureLabs형 캔버스 — compare ↔ preview 토글.
// DESIGN-LANGUAGE §3 카드 radius 18px · §8 모션 250ms cubic-bezier(0.4,0,0.2,1).
// 톤 분리: 앱 chrome = sapphire glass / 캔버스·프리뷰 = white-paper.

type Mode = "compare" | "preview";

const SECTIONS = [
  "Abstract", "Introduction", "Methods", "Results",
  "Discussion", "Conclusion", "Tables", "References",
];

export default function PreviewPane() {
  const [mode, setMode] = useState<Mode>("compare");
  const [activeSection, setActiveSection] = useState<string>("Abstract");

  // TODO: research_state.sections에서 실데이터. Phase 1 깊음 작업 끝나면 useResearchState() hook.
  const sections: Record<string, { current: string; revised?: string }> = {};

  return (
    <aside className="h-full flex flex-col bg-surface-alt border-l border-ink/5 overflow-hidden">
      {/* Toolbar — 상단 sticky */}
      <div className="px-4 py-3 bg-white/80 backdrop-blur-md border-b border-ink/5 flex items-center gap-2">
        <span className="text-xs font-semibold text-ink-subtle tracking-wide uppercase">
          {mode === "compare" ? "Compare" : "Preview"}
        </span>
        <div className="flex-1" />

        {/* 섹션 칩 (compare 모드에서만) */}
        {mode === "compare" && (
          <select
            value={activeSection}
            onChange={(e) => setActiveSection(e.target.value)}
            className="text-xs px-2.5 py-1.5 rounded-full bg-surface-alt border border-ink/10
                         text-ink hover:border-sapphire/30 focus:border-sapphire focus:outline-none
                         transition-colors"
          >
            {SECTIONS.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        )}

        {/* Preview ⤢ 토글 — DESIGN-LANGUAGE §5: 2-pill */}
        <button
          onClick={() => setMode(mode === "compare" ? "preview" : "compare")}
          className="group relative px-3.5 py-1.5 rounded-full bg-sapphire text-white text-xs font-medium
                       shadow-sm shadow-sapphire/20
                       hover:shadow-md hover:shadow-sapphire/30 hover:-translate-y-0.5
                       active:translate-y-0
                       transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]"
          aria-label={mode === "compare" ? "Open preview" : "Back to compare"}
        >
          <span className="inline-flex items-center gap-1.5">
            {mode === "compare" ? (
              <>
                <span>Preview</span>
                <span className="opacity-80 text-[10px]">⤢</span>
              </>
            ) : (
              <>
                <span className="opacity-80">◂</span>
                <span>Edit</span>
              </>
            )}
          </span>
        </button>
      </div>

      {/* 본문 영역 — 모드 전환 카드 플립 */}
      <div className="flex-1 relative overflow-hidden" style={{ perspective: 1600 }}>
        <AnimatePresence mode="wait" initial={false}>
          {mode === "compare" ? (
            <motion.div
              key="compare"
              className="absolute inset-0 overflow-y-auto"
              initial={{ opacity: 0, rotateY: -10, x: -24 }}
              animate={{ opacity: 1, rotateY: 0, x: 0 }}
              exit={{ opacity: 0, rotateY: 10, x: 24 }}
              transition={{ duration: 0.32, ease: [0.4, 0, 0.2, 1] }}
            >
              <BeforeAfter
                section={activeSection}
                before={sections[activeSection]?.current || ""}
                after={sections[activeSection]?.revised}
              />
            </motion.div>
          ) : (
            <motion.div
              key="preview"
              className="absolute inset-0 overflow-y-auto bg-[#fafaf7]"
              initial={{ opacity: 0, rotateY: 10, x: 24 }}
              animate={{ opacity: 1, rotateY: 0, x: 0 }}
              exit={{ opacity: 0, rotateY: -10, x: -24 }}
              transition={{ duration: 0.32, ease: [0.4, 0, 0.2, 1] }}
            >
              <FullPaperPreview sections={sections} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </aside>
  );
}
