"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { api } from "@/lib/api";

// FRONTEND_NEXTJS_SPEC §6.1: 좌측 슬림 레일 (56px) — RECENT는 드로어로.
// DESIGN-LANGUAGE §3 카드 · §8 모션 250ms cubic-bezier.

type Project = {
  id: string;
  title: string;
  updated_at?: number;
};

export default function SlimRail() {
  const [open, setOpen] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open || projects.length > 0) return;
    setLoading(true);
    api<{ projects: Project[] }>("/projects")
      .then((d) => setProjects(d.projects || []))
      .catch((e) => setError(String(e).slice(0, 80)))
      .finally(() => setLoading(false));
  }, [open, projects.length]);

  return (
    <>
      <aside className="h-screen flex flex-col items-center justify-between py-3 px-2
                          bg-white/70 backdrop-blur-md border-r border-ink/5 z-30">
        {/* 상단 — 로고 + 새 채팅 + 햄버거 */}
        <div className="flex flex-col items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-sapphire to-sapphire/70
                          flex items-center justify-center text-white text-sm font-semibold
                          shadow-[0_2px_8px_rgba(31,78,121,0.25)]">
            M
          </div>

          <Link href="/?new=1" aria-label="새 채팅"
                className="group w-9 h-9 rounded-xl bg-sapphire text-white
                              flex items-center justify-center
                              shadow-[0_2px_8px_rgba(31,78,121,0.2)]
                              hover:shadow-[0_4px_14px_rgba(31,78,121,0.3)] hover:-translate-y-0.5
                              transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2.5" strokeLinecap="round">
              <path d="M12 5v14M5 12h14" />
            </svg>
          </Link>

          <button onClick={() => setOpen(true)} aria-label="RECENT"
                  className="group w-9 h-9 rounded-xl bg-white/40 hover:bg-white
                                border border-ink/8 hover:border-sapphire/30
                                text-ink-subtle hover:text-sapphire
                                flex items-center justify-center
                                transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 6h18M3 12h18M3 18h12" />
            </svg>
          </button>
        </div>

        {/* 하단 — 사용자 아바타 (placeholder) */}
        <div className="flex flex-col items-center gap-2">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-ink-muted/30 to-ink-muted/10
                          border border-ink/5 flex items-center justify-center
                          text-[0.7rem] font-medium text-ink-subtle">
            M
          </div>
        </div>
      </aside>

      {/* RECENT 드로어 */}
      <AnimatePresence>
        {open && (
          <>
            <motion.div
              key="backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
              onClick={() => setOpen(false)}
              className="fixed inset-0 bg-ink/15 backdrop-blur-[2px] z-40"
            />
            <motion.aside
              key="drawer"
              initial={{ x: -320, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: -320, opacity: 0 }}
              transition={{ duration: 0.28, ease: [0.4, 0, 0.2, 1] }}
              className="fixed top-0 left-[56px] h-screen w-[320px] bg-white z-50
                           shadow-[8px_0_32px_rgba(34,34,34,0.08)] border-r border-ink/5
                           flex flex-col overflow-hidden"
            >
              {/* 헤더 */}
              <div className="px-5 py-4 flex items-center justify-between border-b border-ink/5">
                <div>
                  <div className="text-[0.62rem] tracking-[0.2em] uppercase text-ink-muted">
                    Recent
                  </div>
                  <div className="text-sm font-semibold text-ink mt-0.5">최근 프로젝트</div>
                </div>
                <button onClick={() => setOpen(false)} aria-label="닫기"
                        className="w-8 h-8 rounded-lg hover:bg-surface-alt text-ink-muted
                                      hover:text-ink transition-colors flex items-center justify-center">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                       strokeWidth="2" strokeLinecap="round">
                    <path d="M6 6l12 12M6 18L18 6" />
                  </svg>
                </button>
              </div>

              {/* 목록 */}
              <div className="flex-1 overflow-y-auto px-3 py-3">
                {loading && (
                  <div className="space-y-2">
                    {[1, 2, 3, 4].map((i) => (
                      <div key={i} className="h-12 rounded-xl bg-ink/5 animate-pulse" />
                    ))}
                  </div>
                )}
                {error && (
                  <div className="px-3 py-4 text-xs text-danger bg-danger/5 rounded-xl">
                    연결 안 됨 — 로그인 확인
                  </div>
                )}
                {!loading && !error && projects.length === 0 && (
                  <div className="px-3 py-8 text-center">
                    <div className="text-3xl text-ink/10 mb-2">¶</div>
                    <div className="text-xs text-ink-muted">
                      아직 프로젝트 없음
                    </div>
                  </div>
                )}
                <ul className="space-y-1">
                  {projects.slice(0, 40).map((p) => (
                    <li key={p.id}>
                      <Link
                        href={`/?pid=${encodeURIComponent(p.id)}`}
                        onClick={() => setOpen(false)}
                        className="group flex items-center gap-3 px-3 py-2.5 rounded-xl
                                      hover:bg-sapphire/5 transition-colors"
                        title={p.title}
                      >
                        <div className="w-1.5 h-1.5 rounded-full bg-sapphire/30
                                          group-hover:bg-sapphire transition-colors" />
                        <span className="text-sm text-ink truncate flex-1
                                            group-hover:text-sapphire transition-colors">
                          {p.title || "제목 없음"}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
