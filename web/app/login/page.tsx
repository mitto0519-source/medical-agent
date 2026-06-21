"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";

// 초대된 이메일만 통과 — 비밀번호 없음 (data/users.json 화이트리스트).
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
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"}/auth/login`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: email.trim().toLowerCase(), password: "" }),
        }
      );
      if (!res.ok) {
        setError("초대받지 않은 이메일입니다.");
        return;
      }
      // full page reload — cookie 동기화 후 middleware 게이트 통과
      window.location.href = redirect || "/";
    } catch {
      setError("서버 연결 실패.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="card w-full max-w-sm anim-slide-in">
      {/* 로고 */}
      <div className="flex items-center gap-2.5 mb-6">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-sapphire to-sapphire/70
                          flex items-center justify-center text-white text-sm font-semibold
                          shadow-[0_2px_8px_rgba(31,78,121,0.25)]">
          M
        </div>
        <div>
          <div className="text-[0.62rem] tracking-[0.2em] uppercase text-ink-muted">
            Medical-Agent
          </div>
          <h1 className="text-base font-semibold tracking-tight text-ink leading-tight">
            로그인
          </h1>
        </div>
      </div>

      {/* 안내 */}
      <p className="text-xs text-ink-subtle leading-relaxed mb-5">
        초대된 이메일로만 접속할 수 있습니다.
      </p>

      <label className="block mb-4">
        <span className="text-xs text-ink-subtle">이메일</span>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoComplete="email"
          autoFocus
          placeholder="you@example.com"
          className="mt-1.5 w-full px-3 py-2.5 border border-ink/10 rounded-xl text-sm
                       focus:border-sapphire focus:outline-none focus:ring-2 focus:ring-sapphire/15
                       transition-all duration-150"
        />
      </label>

      {error && (
        <div className="text-xs text-danger mb-3 bg-danger/5 border border-danger/15 px-3 py-2 rounded-lg">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={submitting || !email.trim()}
        className="w-full py-2.5 bg-sapphire text-white rounded-xl text-sm font-medium
                     shadow-[0_2px_8px_rgba(31,78,121,0.2)]
                     hover:shadow-[0_4px_14px_rgba(31,78,121,0.3)] hover:-translate-y-0.5
                     active:translate-y-0
                     disabled:opacity-40 disabled:translate-y-0 disabled:shadow-none
                     transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]"
      >
        {submitting ? "확인 중…" : "로그인"}
      </button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <main className="min-h-screen flex items-center justify-center px-4
                       bg-[radial-gradient(900px_600px_at_30%_-5%,rgba(31,78,121,0.06),transparent_60%),radial-gradient(800px_500px_at_70%_100%,rgba(31,78,121,0.04),transparent_55%),linear-gradient(180deg,#fff_0%,#f7f7f9_100%)]">
      <Suspense fallback={<div className="text-ink-muted text-sm">로딩…</div>}>
        <LoginForm />
      </Suspense>
    </main>
  );
}
