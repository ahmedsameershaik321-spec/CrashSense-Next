import type { Metadata } from "next";
import { LoginForm } from "@/components/login-form";
import { PublicAuthRedirect } from "@/components/public-auth-redirect";
import { AuthFrame } from "@/components/auth-frame";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Sign in",
};

export default function LoginPage() {
  return (
    <PublicAuthRedirect>
      <AuthFrame
        eyebrow="Secure sign-in"
        title="Welcome back"
        description="Sign in with your CrashSense account to continue to your workspace."
        footer={
          <>
            New to CrashSense?{" "}
            <Link
              className="font-medium text-blue-700 transition hover:text-blue-700"
              href="/register"
            >
              Create an account
            </Link>
          </>
        }
      >
        <LoginForm />
      </AuthFrame>
    </PublicAuthRedirect>
  );
}
