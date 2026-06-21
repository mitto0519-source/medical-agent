"use client";

// DEPRECATED (2026-06-21, 규칙10 중복 제거): 240px RecentSidebar는 SlimRail(56px 레일 + RECENT 드로어)로
// 대체됨. 더 이상 어디서도 import 되지 않음. OneDrive 권한으로 파일 삭제 불가 →
// 중복 로직을 제거하고 단일 원본(SlimRail)으로 재export만 남긴다.
export { default } from "./SlimRail";
