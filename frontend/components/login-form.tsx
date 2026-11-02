"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, LoaderCircle } from "lucide-react";
import { ApiError } from "@/lib/api";
import { authDestination } from "@/lib/auth";
import { useAuth } from "@/components/auth-provider";
import { FormField } from "@/components/form-field";

export function LoginForm() {
  const router = useRouter();
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      const session = await signIn(email, password);
      router.replace(authDestination(session));
    } catch (reason) {
      setError(
        reason instanceof ApiError
          ? reason.message
          : "Sign-in failed. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="space-y-5" method="post" onSubmit={handleSubmit}>
      <FormField
        autoComplete="email"
        id="email"
        label="Work email"
        name="email"
        onChange={(event) => setEmail(event.target.value)}
        placeholder="name@organization.com"
        required
        type="email"
        value={email}
      />
      <div>
        <FormField
          autoComplete="current-password"
          id="password"
          label="Password"
          name="password"
          onChange={(event) => setPassword(event.target.value)}
          placeholder="Enter your password"
          required
          type="password"
          value={password}
        />
      </div>

      {error && (
        <p
          aria-live="polite"
          className="rounded-lg border border-rose-400/20 bg-rose-400/[0.07] px-3.5 py-3 text-sm text-rose-200"
          role="alert"
        >
          {error}
        </p>
      )}

      <button className="primary-button" disabled={isSubmitting} type="submit">
        {isSubmitting ? (
          <>
            <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
            Verifying account
          </>
        ) : (
          <>
            Sign in securely
            <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </>
        )}
      </button>
      <p className="text-center text-xs text-slate-600">
        Access is available to approved monitoring operators and administrators.
      </p>
    </form>
  );
}
