"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

// FRONTEND_NEXTJS_SPEC §6: 좌측 RECENT 사이드바 — /projects API.
// 2026-06-21: placeholder 양식 제거, 실 컴포넌트.

type Project = {
  id: string;
  title: string;
  updated_at?: number;
  status?: string;
};

export default function RecentSidebar() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let alive = true;
    api<{ projects: Project[] }>("/projects")
      .then((d) => {
        if (alive) setProjects(d.projects || []);
      })
      .catch((e) => {
        if (alive) setError(String(e).slice(0, 80));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  function newChat() {
    // 새 채팅 = 빈 project로 진입 (서버에서 id 발급)
    window.location.href = "/?new=1";
  }

  return (
    <aside className="border-r border-ink-muted/15 bg-white overflow-y-auto">
      <div className="p-4 border-b border-ink-muted/15">
        <button
          onClick={newChat}
          className="w-full px-3 py-2 bg-sapphire text-white rounded-md text-sm font-medium hover:bg-sapphire/90 transition-colors"
        >
          + 새 채팅
        </button>
      </div>
      <div className="p-3 text-xs text-ink-muted uppercase tracking-wide">
        RECENT
      </div>
      {loading && (
        <div className="px-4 py-2 text-xs text-ink-muted">불러오는 중…</div>
      )}
      {error && (
        <div className="px-4 py-2 text-xs text-danger">
          연결 안 됨 — 로그인 양식 확인
        </div>
      )}
      {!loading && !error && projects.length === 0 && (
        <div className="px-4 py-2 text-xs text-ink-muted">
          아직 프로젝트 없음. + 새 채팅으로 시작.
        </div>
      )}
      <ul className="px-2 space-y-1">
        {projects.slice(0, 30).map((p) => (
          <li key={p.id}>
            <Link
              href={`/?pid=${encodeURIComponent(p.id)}`}
              className="block px-3 py-2 rounded-md text-sm text-ink hover:bg-surface-alt transition-colors truncate"
              title={p.title}
            >
              {p.title || "제목 없음"}
            </Link>
          </li>
        ))}
      </ul>
    </aside>
  );
}
