import { NextRequest, NextResponse } from "next/server";

// FRONTEND_NEXTJS_SPEC §9: 워크스페이스 인증 게이트.
// 2026-06-21 fix: (app) route group이 URL에 안 박혀 / 가 워크스페이스라
//   "/app" 시작 path 양식 작동 안 함. → public path 화이트리스트로 변경.

const PUBLIC_EXACT = new Set([
  "/login",
  "/landing",
  "/robots.txt",
  "/sitemap.xml",
  "/favicon.ico",
]);

const PUBLIC_PREFIX = [
  "/research/",
  "/concept/",
  "/methods",
  "/_next/",
  "/fastapi/",
  "/api/",
];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // 공개 경로는 무인증 통과
  if (PUBLIC_EXACT.has(pathname)) return NextResponse.next();
  if (PUBLIC_PREFIX.some((p) => pathname.startsWith(p))) return NextResponse.next();

  // 워크스페이스(/, /workspace, etc) = 인증 필요
  const token = req.cookies.get("ma_token")?.value;
  if (!token) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("redirect", pathname);
    return NextResponse.redirect(url);
  }

  // 토큰 존재 확인만 — 유효성 검증은 API에서
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
