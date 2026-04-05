import Link from "next/link";
import {
  MessageSquare,
  FileText,
  Zap,
  ArrowRight,
  Lightbulb,
  Brain,
  Download,
} from "lucide-react";
import { HomeAuthRedirect } from "@/components/home/home-auth-redirect";

const FEATURES = [
  {
    icon: MessageSquare,
    title: "对话式需求挖掘",
    desc: "AI 主动追问，帮你想清楚每个假设背后的逻辑，拒绝模糊，直指核心。",
    accent: false,
  },
  {
    icon: FileText,
    title: "结构化 PRD 输出",
    desc: "对话内容实时沉淀为专业的产品需求文档，覆盖目标用户、核心问题、解决方案与 MVP 范围。",
    accent: true,
  },
  {
    icon: Zap,
    title: "决策风险识别",
    desc: "每轮对话自动标记假设风险与推进建议，让你在正确方向上加速，而不是在迷雾中打转。",
    accent: false,
  },
] as const;

const STEPS = [
  {
    step: "01",
    icon: Lightbulb,
    title: "描述你的想法",
    desc: "用一句话告诉 AI 你在构建什么，不需要完美，粗糙的想法也 OK。",
  },
  {
    step: "02",
    icon: Brain,
    title: "AI 深度追问",
    desc: "AI 联合创始人主动提问、挑战假设、挖掘细节，帮你想清楚所有关键问题。",
  },
  {
    step: "03",
    icon: Download,
    title: "导出 PRD",
    desc: "结构化产品需求文档已经准备好，一键导出为 Markdown，随时分享给团队。",
  },
] as const;

const PARTNERS = ["Founder Studio", "Product Labs", "Venture Works", "Build Co", "Idea Factory", "Launch Hub"];

export default function HomePage() {
  return (
    <>
      <HomeAuthRedirect />
      <div className="min-h-screen bg-[#0a0a0a] text-neutral-200 font-[family-name:var(--font-sans)] overflow-x-hidden">

        {/* ── Announcement bar ── */}
        <div className="w-full bg-gradient-to-r from-[#8a7356] via-[#c6a87c] to-[#8a7356] py-2 px-4 text-center">
          <span className="text-[13px] font-medium text-black">AI Co-founder 现已正式上线&nbsp;&mdash;&nbsp;</span>
          <Link href="/register" className="text-[13px] font-bold text-black underline underline-offset-2 hover:opacity-80">立即免费体验</Link>
        </div>

        {/* ── Nav ── */}
        <header className="sticky top-0 z-40 bg-[#0a0a0a]/80 backdrop-blur-md border-b border-white/5">
          <div className="max-w-[1200px] mx-auto px-6 h-[72px] flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-white rounded-full flex items-center justify-center">
                <Brain className="w-4 h-4 text-black" />
              </div>
              <span className="font-[family-name:var(--font-display)] font-medium text-xl tracking-tight text-white">AI Co-founder</span>
            </div>
            <nav className="hidden md:flex items-center gap-10" aria-label="主导航">
              <span className="text-sm font-medium text-neutral-400 hover:text-white transition-colors cursor-pointer">功能</span>
              <span className="text-sm font-medium text-neutral-400 hover:text-white transition-colors cursor-pointer">案例</span>
              <span className="text-sm font-medium text-neutral-400 hover:text-white transition-colors cursor-pointer">定价</span>
            </nav>
            <div className="flex items-center gap-4">
              <Link
                href="/login"
                className="px-5 py-2.5 text-sm font-medium text-white border border-white/20 rounded-full hover:bg-white/5 transition-colors"
              >
                登录
              </Link>
              <Link
                href="/register"
                className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white border border-white/20 rounded-full hover:bg-white/5 transition-colors"
              >
                免费开始
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </header>

        {/* ── Hero ── */}
        <section className="relative max-w-[1200px] mx-auto px-6 pt-32 pb-24 text-center">
          {/* Decorative circular rings */}
          <div aria-hidden="true" className="absolute top-0 left-0 -translate-x-1/3 -translate-y-1/4 pointer-events-none opacity-20">
            <div className="w-[1000px] h-[1000px] rounded-full border border-white/20 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
            <div className="w-[750px] h-[750px] rounded-full border border-white/20 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
            <div className="w-[500px] h-[500px] rounded-full border border-white/20 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
          </div>
          
          {/* Gold ambient glow */}
          <div aria-hidden="true" className="absolute top-1/4 left-1/2 -translate-x-1/2 w-96 h-64 bg-[#d4af7a]/10 rounded-full blur-[100px] pointer-events-none" />

          <div className="relative z-10">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-[#111] border border-white/10 rounded-full text-neutral-300 text-xs font-medium mb-10">
              AI Co-founder 现已全面 <span className="text-[#d4af7a]">开放注册</span>
            </div>

            <h1 className="font-[family-name:var(--font-display)] text-5xl sm:text-6xl lg:text-[80px] font-medium tracking-tight leading-[1.1] mb-8 text-white">
              产品想法的
              <br />
              <span className="text-[#d4af7a] italic">AI 联合创始人</span>
            </h1>

            <p className="max-w-2xl mx-auto text-[13px] text-neutral-400 tracking-[0.2em] uppercase mb-12">
              持续对话 | 挖掘需求 | 挑战假设 | 沉淀决策
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/login"
                className="inline-flex items-center gap-2 px-7 py-3.5 border border-white/20 text-white text-sm font-medium rounded-full hover:bg-white/5 transition-all"
              >
                已有账号，登录
                <ArrowRight className="w-4 h-4" />
              </Link>
              <Link
                href="/register"
                className="inline-flex items-center gap-2 px-7 py-3.5 bg-white text-black text-sm font-medium rounded-full hover:bg-neutral-200 transition-colors"
              >
                立即开始使用
              </Link>
            </div>
          </div>
        </section>

        {/* ── Product mockup ── */}
        <section className="max-w-[1100px] mx-auto px-6 pb-24 relative z-20">
          <div className="rounded-2xl border border-white/10 bg-[#0f0f0f] overflow-hidden shadow-[0_0_100px_rgba(0,0,0,0.8)]">
            {/* Browser chrome */}
            <div className="flex items-center gap-2 px-4 py-3 bg-[#111] border-b border-white/5">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-white/10" />
                <div className="w-3 h-3 rounded-full bg-white/10" />
                <div className="w-3 h-3 rounded-full bg-white/10" />
              </div>
              <div className="flex-1 mx-4 h-6 bg-white/5 rounded-md flex items-center px-3">
                <span className="text-[10px] text-neutral-500">AI Co-founder Workspace</span>
              </div>
            </div>
            {/* Three-panel workspace */}
            <div className="grid grid-cols-[200px_1fr_230px] divide-x divide-white/5 h-[400px] max-lg:grid-cols-[1fr_200px] max-md:grid-cols-1 bg-[#0a0a0a]">
              {/* Sidebar */}
              <div className="p-4 space-y-2 max-md:hidden">
                <div className="h-5 bg-white/10 rounded w-3/4 mb-4" />
                <div className="h-9 bg-[#d4af7a]/10 border border-[#d4af7a]/20 rounded-md" />
                <div className="h-9 bg-white/5 rounded-md" />
                <div className="h-9 bg-white/5 rounded-md" />
              </div>
              {/* Conversation */}
              <div className="p-6 space-y-6">
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-white/10 shrink-0 flex items-center justify-center">
                    <div className="w-4 h-4 bg-white/20 rounded-full" />
                  </div>
                  <div className="space-y-2 flex-1 pt-1">
                    <div className="h-3 bg-white/10 rounded w-full" />
                    <div className="h-3 bg-white/10 rounded w-5/6" />
                    <div className="h-3 bg-white/10 rounded w-4/6" />
                  </div>
                </div>
                <div className="flex gap-3 justify-end">
                  <div className="space-y-2 max-w-[240px] pt-1">
                    <div className="h-3 bg-[#d4af7a]/20 rounded w-full" />
                    <div className="h-3 bg-[#d4af7a]/20 rounded w-3/4 ml-auto" />
                  </div>
                </div>
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-[#d4af7a]/20 shrink-0 flex items-center justify-center">
                    <Brain className="w-4 h-4 text-[#d4af7a]" />
                  </div>
                  <div className="space-y-2 flex-1 pt-1">
                    <div className="h-3 bg-white/10 rounded w-full" />
                    <div className="h-3 bg-white/10 rounded w-3/4" />
                    <div className="h-3 bg-white/10 rounded w-5/6" />
                    <div className="h-3 bg-[#d4af7a]/20 border border-[#d4af7a]/30 rounded w-1/2 mt-2" />
                  </div>
                </div>
              </div>
              {/* PRD panel */}
              <div className="p-5 space-y-4 max-lg:hidden bg-[#0d0d0d]">
                <div className="h-5 bg-white/10 rounded w-1/2 mb-2" />
                <div className="space-y-2 pt-1">
                  <div className="h-2.5 bg-white/5 rounded w-full" />
                  <div className="h-2.5 bg-white/5 rounded w-5/6" />
                </div>
                <div className="h-5 bg-white/10 rounded w-2/3 mt-6 mb-2" />
                <div className="space-y-2">
                  <div className="h-2.5 bg-[#d4af7a]/10 border border-[#d4af7a]/20 rounded w-full" />
                  <div className="h-2.5 bg-[#d4af7a]/10 border border-[#d4af7a]/20 rounded w-4/5" />
                  <div className="h-2.5 bg-[#d4af7a]/10 border border-[#d4af7a]/20 rounded w-3/5" />
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── Social proof ── */}
        <section className="border-y border-white/5 bg-[#0a0a0a] py-12 relative z-10">
          <div className="max-w-[1200px] mx-auto px-6">
            <p className="text-center text-[11px] text-neutral-500 uppercase tracking-[0.2em] mb-10">
              AI Transformation Partner to the Best
            </p>
            <div className="flex flex-wrap items-center justify-center gap-x-14 gap-y-6 opacity-50 grayscale">
              {PARTNERS.map((name) => (
                <span key={name} className="text-lg font-[family-name:var(--font-display)] italic text-white tracking-wide">
                  {name}
                </span>
              ))}
            </div>
          </div>
        </section>

        {/* ── Features ── */}
        <section className="max-w-[1200px] mx-auto px-6 py-32">
          <div className="text-center mb-20">
            <h2 className="font-[family-name:var(--font-display)] text-4xl sm:text-5xl font-medium tracking-tight mb-4 text-white">
              从模糊想法到<span className="text-[#d4af7a] italic">清晰 PRD</span>
            </h2>
            <p className="text-neutral-400 text-sm tracking-wide uppercase">三个核心能力，让产品定义不再痛苦</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {FEATURES.map(({ icon: Icon, title, desc, accent }) => (
              <div
                key={title}
                className={`rounded-2xl p-8 border transition-colors duration-200 ${
                  accent
                    ? "bg-[#d4af7a]/5 border-[#d4af7a]/20"
                    : "bg-[#111] border-white/5 hover:border-white/10"
                }`}
              >
                <div
                  className={`w-12 h-12 rounded-full flex items-center justify-center mb-6 ${
                    accent ? "bg-[#d4af7a]/10 text-[#d4af7a]" : "bg-white/5 text-neutral-400"
                  }`}
                >
                  <Icon className="w-5 h-5" />
                </div>
                <h3 className="font-[family-name:var(--font-display)] text-xl font-medium mb-3 text-white">{title}</h3>
                <p className={`text-sm leading-relaxed ${accent ? "text-[#d4af7a]/80" : "text-neutral-400"}`}>
                  {desc}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* ── How it works ── */}
        <section className="bg-[#111] border-y border-white/5">
          <div className="max-w-[1200px] mx-auto px-6 py-32">
            <div className="text-center mb-20">
              <h2 className="font-[family-name:var(--font-display)] text-4xl sm:text-5xl font-medium tracking-tight mb-4 text-white">
                三步完成 <span className="italic text-[#d4af7a]">PRD</span>
              </h2>
              <p className="text-neutral-400 text-sm tracking-wide uppercase">简单、快速、专业</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
              {STEPS.map(({ step, icon: Icon, title, desc }) => (
                <div key={step} className="flex flex-col items-center text-center">
                  <div className="w-16 h-16 rounded-full bg-[#0a0a0a] border border-white/10 flex items-center justify-center mb-6 relative">
                    <div className="absolute -top-3 -right-3 text-[10px] font-mono text-[#d4af7a] bg-[#111] px-2 py-0.5 rounded-full border border-white/10">{step}</div>
                    <Icon className="w-6 h-6 text-white" />
                  </div>
                  <h3 className="font-[family-name:var(--font-display)] text-xl font-medium mb-3 text-white">{title}</h3>
                  <p className="text-sm text-neutral-400 leading-relaxed max-w-xs">{desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── CTA ── */}
        <section className="relative overflow-hidden">
          <div aria-hidden="true" className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="w-[800px] h-[400px] bg-[#d4af7a]/10 rounded-full blur-[120px]" />
          </div>
          <div className="relative max-w-[1200px] mx-auto px-6 py-32 text-center">
            <h2 className="font-[family-name:var(--font-display)] text-5xl sm:text-6xl font-medium tracking-tight mb-6 text-white">
              准备好了吗？
            </h2>
            <p className="text-neutral-400 mb-10 max-w-md mx-auto leading-relaxed">
              加入已经在用 AI Co-founder 打磨产品想法的创始人，从今天开始。
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/register"
                className="inline-flex items-center gap-2 px-8 py-4 bg-white text-black text-sm font-medium rounded-full hover:bg-neutral-200 transition-colors"
              >
                免费开始使用
              </Link>
            </div>
          </div>
        </section>

        {/* ── Footer ── */}
        <footer className="border-t border-white/5 bg-[#0a0a0a]">
          <div className="max-w-[1200px] mx-auto px-6 py-10 flex flex-col sm:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-3">
              <div className="w-6 h-6 bg-white rounded-full flex items-center justify-center">
                <Brain className="w-3 h-3 text-black" />
              </div>
              <span className="font-[family-name:var(--font-display)] text-base font-medium text-white">AI Co-founder</span>
            </div>
            <p className="text-[13px] text-neutral-500">&copy; 2026 AI Co-founder. All rights reserved.</p>
            <div className="flex gap-6">
              <Link href="/login" className="text-[13px] text-neutral-500 hover:text-white transition-colors">
                登录
              </Link>
              <Link href="/register" className="text-[13px] text-neutral-500 hover:text-white transition-colors">
                注册
              </Link>
            </div>
          </div>
        </footer>
      </div>
    </>
  );
}
