// FastAPI client — Phase 2 api/main.py 18 routes 소비.
// 모든 요청은 httpOnly 쿠키 (credentials: 'include') 또는 Authorization Bearer.

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export async function api<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${path} → ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json();
}

export const apiUrl = (path: string) => `${API_BASE}${path}`;
