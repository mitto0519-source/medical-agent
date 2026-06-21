"use client";

import ComingSoon from "@/components/ComingSoon";

export default function AnalysisPage() {
  return (
    <ComingSoon
      title="Analysis"
      subtitle="Statistics · Figures · Tables — KYRBS/KNHANES 통계 엔진"
      icon="📊"
      features={[
        "survey-weighted logistic / GEE / 다수준 모델",
        "Forest plot · KM curve · prevalence bar · Table 1/2 일괄 생성",
        "STATA do-file · R script · Python notebook 양식 export",
        "MASLD/MetALD/FIB-4 자동 분류 + 민감도 분석",
      ]}
    />
  );
}
