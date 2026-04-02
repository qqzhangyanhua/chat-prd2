import { AuthForm } from "../../components/auth/auth-form";


export default function RegisterPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-12">
      <AuthForm mode="register" />
    </main>
  );
}
