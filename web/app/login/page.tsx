"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";

// 초대된 이메일만 통과 — 비밀번호 없음 (data/users.json 화이트리스트).
// ★ CRAFT_SPEC §13 / UI_BLUEPRINT R2: 진입 화면 = 다크 atmosphere + 가운데 글래스 카드.
function LoginForm() {
  const params = useSearchParams();
  const redirect = params.get("redirect") || "/";
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
      const res = await fetch(`${base}/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase(), password: "" }),
      });
      if (!res.ok) {
        const t = await res.text().catch(() => "");
        setError(`로그인 실패 (${res.status}): ${t.slice(0, 80) || "초대 이메일 확인"}`);
        return;
      }
      // ★ 2026-06-21 fix: 응답 body 토큰을 localStorage에 백업 + cookie 동기화 대기
      // HF Space 등 일부 환경에서 cookie 동기화 timing 양식 양식 양식 X 양식 양식 X.
      // 응답 body 토큰을 localStorage에 임시 저장 → 다음 페이지 양식 양식 확인 가능.
      try {
        const data = await res.json();
        if (data?.token) {
          localStorage.setItem("ma_token_backup", data.token);
        }
      } catch {}
      // 짧은 대기 후 reload — cookie 양식 양식 양식 양식 양식
      await new Promise((r) => setTimeout(r, 150));
      window.location.replace(redirect || "/");
    } catch (err) {
      setError(`서버 연결 실패: ${String(err).slice(0, 100)}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="relative z-10 w-full max-w-[420px] anim-slide-in flex flex-col items-center"
    >
      {/* 그라데이션 타이틀 (와이드 트래킹) */}
      <div
        className="text-center font-extrabold tracking-[0.14em] text-[2rem] leading-none
                   bg-gradient-to-r from-[#9DBBFF] via-[#2F5EFF] to-[#22D3EE]
                   bg-clip-text text-transparent select-none"
      >
        MEDICAL&nbsp;RESEARCH&nbsp;AGENT
      </div>
      <p className="mt-3.5 mb-8 text-[0.84rem]" style={{ color: "var(--txt-secondary)" }}>
        질문에서 근거, 분석, 논문까지
      </p>

      {/* 글래스 카드 (Surface C · radius 24 · border .08) */}
      <div
        className="surface-c w-full rounded-[24px] px-7 py-7"
        style={{
          boxShadow:
            "0 0 0 1px rgba(255,255,255,.03), 0 24px 60px rgba(0,0,0,.45)",
        }}
      >
        <label className="block">
          <span className="text-[0.78rem] font-medium" style={{ color: "var(--txt-secondary)" }}>
            이메일
          </span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            autoFocus
            placeholder="researcher@medagent.io"
            className="hero-textarea mt-2 w-full h-12 px-4 rounded-[14px] text-sm text-white
                       bg-white/[0.03] outline-none transition-colors duration-150"
            style={{ border: "1px solid var(--border)" }}
            onFocus={(e) => (e.currentTarget.style.borderColor = "var(--border-hover)")}
            onBlur={(e) => (e.currentTarget.style.borderColor = "var(--border)")}
          />
        </label>

        <p className="mt-3 text-[0.72rem]" style={{ color: "var(--txt-muted)" }}>
          초대된 이메일로만 접속할 수 있습니다.
        </p>

        {error && (
          <div className="mt-3 text-xs text-red-300 bg-red-500/10 border border-red-500/20 px-3 py-2 rounded-lg">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting || !email.trim()}
          className="mt-5 w-full h-[50px] rounded-[14px] text-[0.95rem] font-semibold text-white
                     tracking-[0.02em] transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]
                     disabled:opacity-40 disabled:translate-y-0"
          style={{ background: "linear-gradient(120deg, #2F5EFF, #4F7BFF)" }}
          onMouseEnter={(e) => {
            if (!submitting && email.trim()) {
              e.currentTarget.style.transform = "translateY(-1px)";
              e.currentTarget.style.boxShadow = "0 8px 28px rgba(47,94,255,.45)";
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = "translateY(0)";
            e.currentTarget.style.boxShadow = "none";
          }}
        >
          {submitting ? "확인 중…" : "연구 시작하기"}
        </button>
      </div>
    </form>
  );
}

export default function LoginPage() {
  return (
    <main
      className="relative min-h-screen flex items-center justify-center px-4 overflow-hidden"
      style={{ background: "#070A12" }}
    >
      {/* L1 atmosphere — 메시 그라데이션 (로그인은 절제: 어두운 L0 위주) */}
      <div className="atmosphere" style={{ opacity: 0.7 }} />
      <Suspense fallback={<div className="text-sm" style={{ color: "var(--txt-muted)" }}>로딩…</div>}>
        <LoginForm />
      </Suspense>
    </main>
  );
}
