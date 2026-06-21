"use client";

import ComingSoon from "@/components/ComingSoon";

export default function KnowledgePage() {
  return (
    <ComingSoon
      title="Knowledge"
      subtitle="RAG · 지식 그래프 · Novelty 검증"
      icon="🧠"
      features={[
        "PubMed 24K+ 논문 RAG 검색 (BiomedNLP-PubMedBERT)",
        "지식 그래프 탐색 (entity·relation·community)",
        "신규성 검증 (논문 0편 확인 + 인접 영역 비교)",
        "관심 분야 자동 수집 (매일 새 논문 알림)",
      ]}
    />
  );
}
