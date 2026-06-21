"use client";

import ComingSoon from "@/components/ComingSoon";

export default function DashboardPage() {
  return (
    <ComingSoon
      title="Dashboard"
      subtitle="오늘 작업 상태 · 진행 중 프로젝트 · 최근 분석"
      icon="🏠"
      features={[
        "프로젝트 카드 그리드 (썸네일·최근 활동·상태)",
        "오늘 할 일 (사용자 + AI 제안)",
        "최근 분석 결과 미리보기 (forest plot · stat 요약)",
        "RAG 기반 새 논문 알림 (관심 분야 자동 수집)",
      ]}
    />
  );
}
