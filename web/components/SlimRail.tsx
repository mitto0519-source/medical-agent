"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";

// FRONTEND_NEXTJS_SPEC §2.1 IA + §6.1 셸 — 좌측 슬림 레일 (56px).
// 7 nav (Dashboard·Projects·Manuscripts·Analysis·Knowledge·References·Settings) + RECENT 드로어.

type NavItem = {
  href: string;
  label: string;
  icon: React.ReactNode;
};

type Project = {
  id: string;
  title: string;
  updated_at?: number;
};

const NAV: NavItem[] = [
  {
    href: "/dashboard", label: "Dashboard",
    icon: <path d="M3 12l9-9 9 9M5 10v10h14V10" />,
  },
  {
    href: "/", label: "Projects",
    icon: <><rect x="4" y="6" width="16" height="14" rx="2"/><path d="M9 3h6v3H9z"/></>,
  },
  {
    href: "/manuscripts", label: "Manuscripts",
    icon: <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z M14 3v6h6 M8 13h8 M8 17h5" />,
  },
  {
    href: "/analysis", label: "Analysis",
    icon: <path d="M4 19h16 M7 16V8 M12 16V4 M17 16v-6" />,
  },
  {
    href: "/knowledge", label: "Knowledge",
    icon: <><circle cx="12" cy="12" r="3"/><circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="5" cy="18" r="2"/><circle cx="19" cy="18" r="2"/><path d="M7 7l4 4 M17 7l-4 4 M7 17l4-4 M17 17l-4-4"/></>,
  },
  {
    href: "/references", label: "References",
    icon: <path d="M4 6h16M4 12h16M4 18h10" />,
  },
  {
    href: "/settings", label: "Settings",
    icon: <><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.6-2-3.4-2.4.8a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.4a7 7 0 0 0-2 1.2L5.1 5.8l-2 3.4 2 1.6A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.6 2 3.4 2.4-.8a7 7 0 0 0 2 1.2L10 21h4l.5-2.4a7 7 0 0 0 2-1.2l2.4.8 2-3.4-2-1.6c.1-.4.1-.8.1-1.2z"/></>,
  },
];

export default function SlimRail() {
  const pathname = usePathname();
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

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/" || pathname === "";
    return pathname?.startsWith(href);
  };

  return (
    <>
      <aside className="h-screen flex flex-col items-center py-3 px-2
                          bg-white/70 backdrop-blur-md border-r border-ink/5 z-30">
        {/* 로고 */}
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-sapphire to-sapphire/70
                          flex items-center justify-center text-white text-sm font-semibold
                          shadow-[0_2px_8px_rgba(31,78,121,0.25)] mb-4">
          M
        </div>

        {/* 새 채팅 */}
        <Link href="/?new=1" aria-label="새 채팅"
              className="group w-9 h-9 rounded-xl bg-sapphire text-white
                            flex items-center justify-center
                            shadow-[0_2px_8px_rgba(31,78,121,0.2)]
                            hover:shadow-[0_4px_14px_rgba(31,78,121,0.3)] hover:-translate-y-0.5
                            transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] mb-1">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2.5" strokeLinecap="round">
            <path d="M12 5v14M5 12h14" />
          </svg>
        </Link>

        {/* 햄버거 → RECENT 드로어 */}
        <button onClick={() => setOpen(true)} aria-label="최근"
                className="w-9 h-9 rounded-xl text-ink-muted hover:bg-sapphire/5 hover:text-sapphire
                              flex items-center justify-center
                              transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] mb-3">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" strokeLinecap="round">
            <path d="M3 6h18M3 12h18M3 18h12" />
          </svg>
        </button>

        {/* 구분선 */}
        <div className="w-6 h-px bg-ink/10 mb-2" />

        {/* IA 7 nav */}
        <nav className="flex flex-col items-center gap-0.5">
          {NAV.map((n) => {
            const active = isActive(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                title={n.label}
                aria-label={n.label}
                className={
                  "relative group w-9 h-9 rounded-xl flex items-center justify-center " +
                  "transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] " +
                  (active
                    ? "bg-sapphire/10 text-sapphire"
                    : "text-ink-muted hover:bg-sapphire/5 hover:text-sapphire")
                }
              >
                {/* 활성 인디케이터 (좌측 막대) */}
                {active && (
                  <span className="absolute -left-2 top-1/2 -translate-y-1/2 w-0.5 h-5
                                    rounded-r-full bg-sapphire" />
                )}
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  {n.icon}
                </svg>

                {/* 툴팁 — hover 시 우측에 슬라이드 */}
                <span className="pointer-events-none absolute left-full ml-3 px-2.5 py-1
                                    rounded-lg bg-ink text-white text-[0.7rem] font-medium
                                    whitespace-nowrap opacity-0 -translate-x-1
                                    group-hover:opacity-100 group-hover:translate-x-0
                                    transition-all duration-150 z-50
                                    shadow-[0_4px_12px_rgba(34,34,34,0.15)]">
                  {n.label}
                </span>
              </Link>
            );
          })}
        </nav>

        {/* 하단 — 아바타 */}
        <div className="mt-auto pt-3 border-t border-ink/5 w-full flex justify-center">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-ink-muted/30 to-ink-muted/10
                          border border-ink/5 flex items-center justify-center
                          text-[0.7rem] font-medium text-ink-subtle cursor-pointer
                          hover:border-sapphire/30 transition-colors">
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
                    <div className="text-xs text-ink-muted">아직 프로젝트 없음</div>
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
