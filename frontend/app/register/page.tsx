import type { Metadata } from "next";
import Link from "next/link";
import { AuthFrame } from "@/components/auth-frame";
import { PublicAuthRedirect } from "@/components/public-auth-redirect";
import { RegistrationForm } from "@/components/registration-form";

export const metadata: Metadata = {
  title: "Request access",
};

export default function RegisterPage() {
  return (
    <PublicAuthRedirect>
      <AuthFrame
        eyebrow="Request access"
        title="Create your account"
        description="Register to request access to the CrashSense monitoring workspace."
        footer={
          <>
            Already registered?{" "}
            <Link
              className="font-medium text-sky-300 transition hover:text-sky-200"
              href="/login"
            >
              Sign in
            </Link>
          </>
        }
      >
        <RegistrationForm />
      </AuthFrame>
    </PublicAuthRedirect>
  );
}
