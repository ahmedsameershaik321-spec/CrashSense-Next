"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { ArrowLeft, CheckCircle2, LoaderCircle, ShieldCheck } from "lucide-react";
import { ApiError, register, type RegisterResponse } from "@/lib/api";
import { FormField } from "@/components/form-field";

export function RegistrationForm() {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [registration, setRegistration] = useState<RegisterResponse | null>(
    null,
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (password !== confirmation) {
      setError("Passwords do not match.");
      return;
    }
    setIsSubmitting(true);
    try {
      const result = await register({
        first_name: firstName,
        last_name: lastName || undefined,
        email,
        password,
      });
      setRegistration(result);
    } catch (reason) {
      setError(
        reason instanceof ApiError
          ? reason.message
          : "Registration failed. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  if (registration) {
    return (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5">
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-50 text-emerald-800">
          <CheckCircle2 aria-hidden="true" className="h-5 w-5" />
        </span>
        <h3 className="mt-4 text-base font-semibold text-slate-900">
          Request received
        </h3>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          {registration.message}
        </p>
        <p className="mt-3 text-xs leading-5 text-slate-500">
          Your account has pending access. An administrator must approve your
          account before operational features are available.
        </p>
        <Link className="primary-button mt-5" href="/login">
          Continue to sign in
        </Link>
      </div>
    );
  }

  return (
    <form className="space-y-4" method="post" onSubmit={handleSubmit}>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField
          autoComplete="given-name"
          id="first-name"
          label="First name"
          maxLength={100}
          name="first_name"
          onChange={(event) => setFirstName(event.target.value)}
          placeholder="First name"
          required
          value={firstName}
        />
        <FormField
          autoComplete="family-name"
          id="last-name"
          label="Last name"
          maxLength={100}
          name="last_name"
          onChange={(event) => setLastName(event.target.value)}
          placeholder="Last name"
          value={lastName}
        />
      </div>
      <FormField
        autoComplete="email"
        id="register-email"
        label="Work email"
        name="email"
        onChange={(event) => setEmail(event.target.value)}
        placeholder="name@organization.com"
        required
        type="email"
        value={email}
      />
      <FormField
        autoComplete="new-password"
        id="register-password"
        label="Password"
        maxLength={128}
        minLength={12}
        name="password"
        onChange={(event) => setPassword(event.target.value)}
        placeholder="At least 12 characters"
        required
        type="password"
        value={password}
      />
      <FormField
        autoComplete="new-password"
        id="confirm-password"
        label="Confirm password"
        maxLength={128}
        minLength={12}
        name="password_confirmation"
        onChange={(event) => setConfirmation(event.target.value)}
        placeholder="Re-enter your password"
        required
        type="password"
        value={confirmation}
      />
      <div className="flex gap-2 rounded-lg border border-line bg-slate-50 p-3 text-xs leading-5 text-slate-600">
        <ShieldCheck
          aria-hidden="true"
          className="mt-0.5 h-4 w-4 shrink-0 text-accent"
        />
        Public registration requests pending access. Operational roles can
        only be assigned by an authorized administrator.
      </div>
      {error && (
        <p
          aria-live="polite"
          className="rounded-lg border border-rose-200 bg-rose-50 px-3.5 py-3 text-sm text-rose-700"
          role="alert"
        >
          {error}
        </p>
      )}
      <button className="primary-button" disabled={isSubmitting} type="submit">
        {isSubmitting ? (
          <>
            <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
            Sending request
          </>
        ) : (
          <>
            Request account access
            <ArrowLeft aria-hidden="true" className="h-4 w-4 rotate-180" />
          </>
        )}
      </button>
    </form>
  );
}
