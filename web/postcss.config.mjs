// PostCSS — Tailwind 3 표준 양식 (2026-06-21).
// ★ 이 파일 누락이 cycle 0e13061~2bd7de5 빌드 양식 Tailwind CSS 안 먹힌 단일원인.
// 빌드 시 @tailwind base/components/utilities directive가 처리 안 되고 그대로 텍스트로 박힘.
// → globals.css가 비어있는 양식이 되어 Tailwind 클래스 적용 X (bg-sapphire, grid-cols, 등 다 무효).

export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
