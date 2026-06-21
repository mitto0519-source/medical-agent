"use client";

import ComingSoon from "@/components/ComingSoon";

export default function ManuscriptsPage() {
  return (
    <ComingSoon
      title="Manuscripts"
      subtitle="Draft · Submitted · Published — 모든 원고 관리"
      icon="📄"
      features={[
        "Draft 보관함 (작성 중 IMRaD 섹션별)",
        "Submitted 추적 (저널·심사 단계·예상 결과)",
        "Word + EndNote CWYW 양식 일괄 export",
        "버전 관리 (이전 수정안 비교 + accept/reject 이력)",
      ]}
    />
  );
}
