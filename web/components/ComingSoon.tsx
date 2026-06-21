"use client";

import Link from "next/link";

type Props = {
  title: string;
  subtitle: string;
  icon: string;
  features: string[];
};

// 페이지가 아직 비어 있을 때 — DESIGN-LANGUAGE §4 empty 상태 정합.
// 단순 "404"가 아니라 무엇이 들어올지 미리보기.
export default function ComingSoon({ title, subtitle, icon, features }: Props) {
  return (
    <div className="flex-1 overflow-y-auto px-6 py-10">
      <div className="max-w-2xl mx-auto">
        {/* 헤더 */}
        <div className="anim-slide-in flex items-start gap-4 mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-sapphire/15 to-sapphire/5
                            border border-sapphire/10 flex items-center justify-center
                            text-2xl flex-shrink-0">
            {icon}
          </div>
          <div className="flex-1 pt-1">
            <div className="text-[0.62rem] tracking-[0.2em] uppercase text-sapphire mb-1">
              Coming soon
            </div>
            <h1 className="text-[1.5rem] font-semibold tracking-tight text-ink leading-tight">
              {title}
            </h1>
            <p className="text-sm text-ink-subtle mt-1.5 leading-relaxed">
              {subtitle}
            </p>
          </div>
        </div>

        {/* 미리보기 카드 */}
        <div className="anim-slide-in card mb-6" style={{ animationDelay: "60ms" }}>
          <div className="text-[0.7rem] font-semibold tracking-[0.15em] uppercase text-ink-muted mb-3">
            예정 기능
          </div>
          <ul className="space-y-3">
            {features.map((f, i) => (
              <li key={i} className="flex items-start gap-3 text-sm text-ink leading-relaxed">
                <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-sapphire/40 flex-shrink-0" />
                <span>{f}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* 현재 가능한 작업 안내 */}
        <div className="anim-slide-in flex items-center justify-between gap-3
                          rounded-2xl bg-gradient-to-br from-sapphire/5 to-sapphire/0
                          border border-sapphire/10 px-5 py-4"
             style={{ animationDelay: "120ms" }}>
          <div>
            <div className="text-sm font-medium text-ink">지금 가능한 작업</div>
            <div className="text-xs text-ink-subtle mt-0.5">
              메인 워크스페이스에서 채팅 + Before/After + Preview 양식 사용 가능
            </div>
          </div>
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full
                         bg-sapphire text-white text-xs font-medium
                         shadow-[0_2px_8px_rgba(31,78,121,0.2)]
                         hover:shadow-[0_4px_14px_rgba(31,78,121,0.3)] hover:-translate-y-0.5
                         transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]"
          >
            워크스페이스로
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2.5" strokeLinecap="round">
              <path d="M5 12h14M13 5l7 7-7 7" />
            </svg>
          </Link>
        </div>
      </div>
    </div>
  );
}
