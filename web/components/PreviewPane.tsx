"use client";

import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import BeforeAfter from "./BeforeAfter";
import FullPaperPreview from "./FullPaperPreview";
import TipTapManuscript from "./preview/TipTapManuscript";

// FRONTEND_NEXTJS_SPEC §6.1~6.4 + UI_BLUEPRINT R5 (Lovable 프리뷰 모드 토글):
//   우측 캔버스를 Preview·Compare·Edit·Tables·Figures·Sources 로 분리한 세그먼트 토글.
//   톤 분리: 앱 chrome = sapphire glass / 캔버스 = white-paper.

type Mode = "preview" | "compare" | "edit" | "tables" | "figures" | "sources";

const MODES: { id: Mode; label: string }[] = [
  { id: "preview", label: "Preview" },
  { id: "compare", label: "Compare" },
  { id: "edit", label: "Edit" },
  { id: "tables", label: "Tables" },
  { id: "figures", label: "Figures" },
  { id: "sources", label: "Sources" },
];

const SECTIONS = [
  "Abstract", "Introduction", "Methods", "Results",
  "Discussion", "Conclusion", "Tables", "References",
];

export default function PreviewPane() {
  const [mode, setMode] = useState<Mode>("preview");
  const [activeSection, setActiveSection] = useState<string>("Abstract");

  // TODO: research_state.sections에서 실데이터 (useResearchState() hook, Phase 1).
  const sections: Record<string, { current: string; revised?: string }> = {};

  // Edit(TipTap)용 flatten — {section: current}
  const editSections = useMemo(() => {
    const o: Record<string, string> = {};
    for (const [k, v] of Object.entries(sections)) o[k] = v.current;
    return o;
  }, [sections]);

  return (
    <aside className="h-full flex flex-col bg-surface-alt border-l border-ink/5 overflow-hidden">
      {/* Toolbar — 세그먼트 토글 */}
      <div className="px-4 py-3 bg-white/80 backdrop-blur-md border-b border-ink/5 flex items-center gap-3">
        <div className="seg-group overflow-x-auto">
          {MODES.map((m) => (
            <button key={m.id} data-on={mode === m.id} onClick={() => setMode(m.id)} className="seg-btn">
              {m.label}
            </button>
          ))}
        </div>

        {/* 섹션 선택 (compare/edit에서) */}
        {(mode === "compare") && (
          <select
            value={activeSection}
            onChange={(e) => setActiveSection(e.target.value)}
            className="ml-auto text-xs px-2.5 py-1.5 rounded-full bg-surface-alt border border-ink/10
                       text-ink hover:border-sapphire/30 focus:border-sapphire focus:outline-none transition-colors"
          >
            {SECTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        )}
        <span className="ml-auto text-[0.68rem] text-ink-muted tabular-nums">manuscript</span>
      </div>

      {/* 본문 — 모드 전환 */}
      <div className="flex-1 relative overflow-hidden">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={mode}
            className="absolute inset-0 overflow-y-auto"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.24, ease: [0.4, 0, 0.2, 1] }}
          >
            {mode === "preview" && (
              <div className="bg-[#fafaf7] min-h-full"><FullPaperPreview sections={sections} /></div>
            )}
            {mode === "compare" && (
              <BeforeAfter
                section={activeSection}
                before={sections[activeSection]?.current || ""}
                after={sections[activeSection]?.revised}
              />
            )}
            {mode === "edit" && (
              <div className="bg-white min-h-full">
                <TipTapManuscript sections={editSections} readOnly={false} />
              </div>
            )}
            {mode === "tables" && (
              <EmptyState icon="▦" title="표가 여기 표시됩니다"
                desc="분석을 실행하면 Table 1(기저특성)·Table 2(aHR/CI) 가 engine 렌더되어 채워집니다." />
            )}
            {mode === "figures" && (
              <EmptyState icon="∿" title="Figure가 여기 표시됩니다"
                desc="KM 곡선·forest plot 등 실데이터 figure(diffusion 아님, lifelines/matplotlib 벡터)가 생성되면 표시됩니다." />
            )}
            {mode === "sources" && (
              <EmptyState icon="▤" title="데이터·레퍼런스"
                desc="업로드한 KNHANES/KYRBS(.sav/.csv)와 참고 PDF가 여기에 모입니다." />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </aside>
  );
}

function EmptyState({ icon, title, desc }: { icon: string; title: string; desc: string }) {
  return (
    <div className="h-full flex items-center justify-center px-10 text-center">
      <div className="max-w-xs">
        <div className="text-4xl text-ink/10 mb-3">{icon}</div>
        <div className="text-sm font-medium text-ink-subtle mb-1.5">{title}</div>
        <p className="text-[0.78rem] text-ink-muted leading-relaxed">{desc}</p>
      </div>
    </div>
  );
}
