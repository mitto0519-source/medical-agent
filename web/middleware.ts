import { NextRequest, NextResponse } from "next/server";

// FRONTEND_NEXTJS_SPEC §9: (app)/** 인증 게이트.
// httpOnly 쿠키 `ma_token` 없으면 /login으로 리다이렉트. (public)·api는 무인증.

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // 워크스페이스만 게이트
  if (!pathname.startsWith("/app")) {
    return NextResponse.next();
  }

  const token = req.cookies.get("ma_token")?.value;
  if (!token) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("redirect", pathname);
    return NextResponse.redirect(url);
  }

  // 토큰 검증은 FastAPI /me에 위임 (Phase 2에서 검증 — middleware는 존재만 체크).
  return NextResponse.next();
}

export const config = {
  matcher: ["/app/:path*"],
};
