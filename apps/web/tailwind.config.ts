import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "-apple-system", "sans-serif"],
        serif: ["var(--font-display)", "Georgia", "serif"],
      },
      colors: {
        brand: {
          primary: "#c59d72",   // 金棕色 - 主品牌色
          accent: "#db7e5b",    // 橙棕色 - 强调色
          dark: "#2b2a27",      // 深灰棕 - 主内容区背景
          darker: "#363432",    // 更深灰棕 - 输入框背景
        },
        surface: {
          light: "#fcfcfb",     // 极浅 - 页面背景
          sidebar: "#faf9f7",   // 浅土色 - 侧边栏背景
          elevated: "#f5efe6",  // 浅金 - 高亮背景
        },
        'border-subtle': "#f0ece5",    // 淡土色边框
        'border-light': "#ebe7e0",     // 更淡的边框
        content: {
          light: "#e8e6e3",     // 浅色文字（深色背景用）
          muted: "#8a8782",     // 次要浅色文字（深色背景用）
          dark: "#7d6041",      // 深色文字（浅色背景用）
        },
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
    },
  },
  plugins: [],
};

export default config;
