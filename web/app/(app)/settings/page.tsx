"use client";

import ComingSoon from "@/components/ComingSoon";

export default function SettingsPage() {
  return (
    <ComingSoon
      title="Settings"
      subtitle="프로필 · API 키 · 모델 · 테마"
      icon="⚙️"
      features={[
        "프로필 (이름·이메일·소속 + 본인 논문 PDF 업로드)",
        "API 키 (Claude · OpenAI · Gemini — failover 우선순위)",
        "모델 라우팅 (task별 Haiku/Sonnet/Opus 선택)",
        "테마 + 언어 (light/dark · ko/en)",
      ]}
    />
  );
}
