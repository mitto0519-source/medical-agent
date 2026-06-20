"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

// (public) — /login. POST /auth/login → httpOnly 쿠키 ma_token → /app redirect.
// ★ 2026-06-21: Next.js 15 SSG 양식 — useSearchParams는 <Suspense> boundary 안에서만.
function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const redirect = params.get("redirect") || "/";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
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
          body: JSON.stringify({ email, password }),
        }
      );
      if (!res.ok) {
        setError("이메일 또는 비밀번호가 올바르지 않습니다.");
        return;
      }
      router.push(redirect);
    } catch {
      setError("서버 연결 실패. /api 가 켜져 있는지 확인.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="card w-full max-w-sm">
      <h1 className="text-xl font-semibold mb-4 text-sapphire">로그인</h1>
      <label className="block mb-3">
        <span className="text-sm text-ink-subtle">이메일</span>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoComplete="email"
          className="mt-1 w-full px-3 py-2 border border-ink-muted/20 rounded-md text-sm"
        />
      </label>
      <label className="block mb-4">
        <span className="text-sm text-ink-subtle">비밀번호</span>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="current-password"
          className="mt-1 w-full px-3 py-2 border border-ink-muted/20 rounded-md text-sm"
        />
      </label>
      {error && (
        <div className="text-sm text-danger mb-3 bg-danger/5 px-3 py-2 rounded">
          {error}
        </div>
      )}
      <button
        type="submit"
        disabled={submitting}
        className="w-full py-2.5 bg-sapphire text-white rounded-md font-medium disabled:opacity-50"
      >
        {submitting ? "..." : "로그인"}
      </button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-surface-alt">
      <Suspense fallback={<div className="text-ink-muted">로딩…</div>}>
        <LoginForm />
      </Suspense>
    </main>
  );
}
