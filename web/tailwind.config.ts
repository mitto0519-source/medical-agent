import type { Config } from "tailwindcss";

// ★ DESIGN.md (sapphire_glass) + DESIGN-LANGUAGE.md craft 규칙 토큰 이식.
// 강제: design_lint (src/design/design_lint.py) 가 빌드 전 검사.
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // primary: sapphire (DESIGN.md primary.navy)
        sapphire: {
          DEFAULT: "#1f4e79",
          50: "#eef3f8",
          900: "#0f2742",
        },
        maroon: "#7d2e2e",
        // neutral — 순흑/순백 금지 (DESIGN-LANGUAGE §1)
        ink: {
          DEFAULT: "#222222",
          subtle: "#555555",
          muted: "#888888",
        },
        surface: {
          DEFAULT: "#ffffff",
          alt: "#f7f7f9",
          panel: "#eef3f8",
        },
        // semantic
        success: "#1f6e3a",
        warning: "#a26b00",
        danger: "#a02828",
      },
      borderRadius: {
        // DESIGN_GOVERNANCE allowed scale (4의 배수)
        none: "0",
        xs: "2px",
        sm: "4px",
        md: "8px",
        lg: "12px",
        xl: "16px",
        "2xl": "24px",
      },
      boxShadow: {
        // DESIGN-LANGUAGE §1: 그림자 4~8% 거의 안 보이게
        glass: "0 1px 3px rgba(31, 78, 121, 0.04), 0 4px 12px rgba(31, 78, 121, 0.06)",
        "glass-md": "0 2px 6px rgba(31, 78, 121, 0.05), 0 8px 24px rgba(31, 78, 121, 0.08)",
      },
      fontFamily: {
        sans: ["Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", "system-ui", "sans-serif"],
        serif: ["Source Serif Pro", "Noto Serif KR", "Times New Roman", "serif"],
        mono: ["JetBrains Mono", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
