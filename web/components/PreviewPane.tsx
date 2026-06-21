"use client";

import { useState } from "react";

// FRONTEND_NEXTJS_SPEC §6: 우측 라이브 프리뷰 — manuscript.sections 양식 docx preview.
// 2026-06-21: placeholder 양식 제거, 실 컴포넌트 (TipTap 양식은 다음 cycle 양식).

type Tab = "manuscript" | "stat" | "figures" | "refs";

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "manuscript", label: "본문", icon: "📄" },
  { id: "stat", label: "통계", icon: "📊" },
  { id: "figures", label: "그림", icon: "🖼" },
  { id: "refs", label: "참고문헌", icon: "🔗" },
];

export default function PreviewPane() {
  const [tab, setTab] = useState<Tab>("manuscript");

  return (
    <aside className="border-l border-ink-muted/15 bg-white h-full flex flex-col overflow-hidden">
      {/* 탭 헤더 (DESIGN-LANGUAGE §5: 5개 미만 → pill 양식) */}
      <div className="flex border-b border-ink-muted/15 px-2 pt-3 gap-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={
              "px-3 py-1.5 text-xs rounded-md transition-colors " +
              (tab === t.id
                ? "bg-sapphire/10 text-sapphire font-medium"
                : "text-ink-subtle hover:bg-surface-alt")
            }
          >
            <span className="mr-1">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>

      {/* 본문 영역 */}
      <div className="flex-1 overflow-y-auto p-5">
        {tab === "manuscript" && <ManuscriptView />}
        {tab === "stat" && (
          <div className="text-sm text-ink-subtle">
            통계 결과는 채팅에서 분석 실행 후 표시됩니다.
          </div>
        )}
        {tab === "figures" && (
          <div className="text-sm text-ink-subtle">
            Figure는 forest/KM/prevalence 등 생성 후 표시됩니다.
          </div>
        )}
        {tab === "refs" && (
          <div className="text-sm text-ink-subtle">
            PMID 인용은 RAG/PubMed 검색 후 누적됩니다.
          </div>
        )}
      </div>
    </aside>
  );
}

function ManuscriptView() {
  // 8 IMRaD 섹션 양식 스켈레톤. 채팅에서 patch_preview 호출 시 채워짐.
  const sections = [
    "Abstract",
    "Introduction",
    "Methods",
    "Results",
    "Discussion",
    "Conclusion",
    "Tables",
    "References",
  ];
  return (
    <div className="space-y-4">
      <div className="text-xs text-ink-muted">
        채팅에서 분석/작성을 요청하면 이곳에 본문이 실시간으로 채워집니다.
      </div>
      {sections.map((s) => (
        <section key={s} className="border-l-2 border-ink-muted/15 pl-3">
          <h3 className="text-sm font-semibold text-ink mb-1">{s}</h3>
          <div className="text-xs text-ink-muted italic">(비어 있음)</div>
        </section>
      ))}
    </div>
  );
}
