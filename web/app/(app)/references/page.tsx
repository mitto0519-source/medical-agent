"use client";

import ComingSoon from "@/components/ComingSoon";

export default function ReferencesPage() {
  return (
    <ComingSoon
      title="References"
      subtitle="인용 관리 · PMID 검증 · EndNote 양식 export"
      icon="🔗"
      features={[
        "프로젝트별 인용 누적 (PMID + DOI 자동 검증)",
        "EndNote CWYW 필드 임베드 (Word docx 양식)",
        "Citation graph (어떤 논문이 어디서 인용되는지)",
        "Vancouver / AMA / APA 양식 변환",
      ]}
    />
  );
}
