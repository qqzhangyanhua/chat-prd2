import { AuthForm } from "../../components/auth/auth-form";

export default function LoginPage() {
  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-brand-dark px-6 py-12">
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none p-4 md:p-12">
        <div className="w-full h-full max-w-[1400px] bg-brand-darker/40 rounded-[48px] md:rounded-[80px] shadow-2xl border border-white/5"></div>
      </div>
      <div className="relative z-10 w-full max-w-[400px]">
        <AuthForm mode="login" />
      </div>
    </main>
  );
}
