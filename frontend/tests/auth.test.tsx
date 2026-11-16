import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "@/components/auth-provider";
import { AuthGate } from "@/components/auth-gate";
import { LoginForm } from "@/components/login-form";
import { RegistrationForm } from "@/components/registration-form";
import { authDestination, canAccessMonitoring } from "@/lib/auth";
import { register } from "@/lib/api";
import type { CurrentUser } from "@/lib/api";

const { routerReplace } = vi.hoisted(() => ({
  routerReplace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ replace: routerReplace }),
}));

const activeOperator: CurrentUser = {
  id: "operator-id",
  email: "operator@example.com",
  first_name: "Casey",
  last_name: "Operator",
  role: "monitoring_operator",
  is_active: true,
  is_email_verified: true,
  approved_at: "2026-01-01T00:00:00Z",
  created_at: "2025-12-01T00:00:00Z",
};

function AuthControls() {
  const { session, signIn, signOut } = useAuth();
  return (
    <div>
      <output>{session?.user.email ?? "Signed out"}</output>
      <button
        onClick={() => void signIn("operator@example.com", "correct-password")}
        type="button"
      >
        Test sign in
      </button>
      <button onClick={signOut} type="button">
        Test sign out
      </button>
    </div>
  );
}

describe("frontend authentication integration", () => {
  it("uses the backend login and profile endpoints and clears session on logout", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: "test-access-token",
            token_type: "bearer",
            expires_in: 900,
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(activeOperator), { status: 200 }),
      )
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    render(
      <AuthProvider>
        <AuthControls />
      </AuthProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Test sign in" }));
    await waitFor(() => {
      expect(screen.getByText("operator@example.com")).toBeInTheDocument();
    });
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/backend-api/api/v1/auth/login",
    );
    expect(fetchMock.mock.calls[1][0]).toBe("/backend-api/api/v1/auth/me");
    expect(fetchMock.mock.calls[1][1]).toMatchObject({
      headers: { Authorization: "Bearer test-access-token" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Test sign out" }));
    expect(screen.getByText("Signed out")).toBeInTheDocument();
  });

  it("registers without a role so the backend assigns pending access", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          message: "Registration successful.",
          user_id: "new-user",
          role: "pending",
        }),
        { status: 201 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await register({
      first_name: "Taylor",
      last_name: "Applicant",
      email: "taylor@example.com",
      password: "A-long-password-123",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/backend-api/api/v1/auth/register",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          first_name: "Taylor",
          last_name: "Applicant",
          email: "taylor@example.com",
          password: "A-long-password-123",
        }),
      }),
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).not.toHaveProperty(
      "role",
    );
  });

  it("does not expose credentials in a GET URL before form hydration", () => {
    const { unmount } = render(
      <AuthProvider>
        <LoginForm />
      </AuthProvider>,
    );
    expect(
      screen.getByRole("button", { name: "Sign in securely" }).closest("form"),
    ).toHaveAttribute("method", "post");

    unmount();
    render(<RegistrationForm />);
    expect(
      screen
        .getByRole("button", { name: "Request account access" })
        .closest("form"),
    ).toHaveAttribute("method", "post");
  });

  it("lets users show and hide passwords on login and registration", () => {
    const login = render(
      <AuthProvider>
        <LoginForm />
      </AuthProvider>,
    );
    const loginPassword = within(login.container).getByLabelText("Password");
    expect(loginPassword).toHaveAttribute("type", "password");
    fireEvent.click(within(login.container).getByRole("button", { name: "Show password" }));
    expect(loginPassword).toHaveAttribute("type", "text");
    fireEvent.click(within(login.container).getByRole("button", { name: "Hide password" }));
    expect(loginPassword).toHaveAttribute("type", "password");

    login.unmount();
    const registration = render(<RegistrationForm />);
    const registrationPassword = registration.container.querySelector<HTMLInputElement>("#register-password");
    const confirmation = registration.container.querySelector<HTMLInputElement>("#confirm-password");
    expect(registrationPassword).not.toBeNull();
    expect(confirmation).not.toBeNull();
    fireEvent.click(within(registration.container).getByRole("button", { name: "Show password" }));
    expect(registrationPassword).toHaveAttribute("type", "text");
    expect(confirmation).toHaveAttribute("type", "password");
    fireEvent.click(within(registration.container).getByRole("button", { name: "Show confirm password" }));
    expect(confirmation).toHaveAttribute("type", "text");
  });

  it("blocks pending and inactive users from operational routes", () => {
    const pending = { ...activeOperator, role: "pending", is_active: false };
    const inactiveOperator = { ...activeOperator, is_active: false };
    const activeAdmin = { ...activeOperator, role: "administrator" };

    expect(canAccessMonitoring(pending)).toBe(false);
    expect(authDestination({ accessToken: "pending", user: pending })).toBe(
      "/access-pending",
    );
    expect(canAccessMonitoring(inactiveOperator)).toBe(false);
    expect(authDestination({ accessToken: "inactive", user: inactiveOperator }))
      .toBe("/access-pending");
    expect(canAccessMonitoring(activeAdmin)).toBe(true);
    expect(authDestination({ accessToken: "admin", user: activeAdmin })).toBe(
      "/dashboard",
    );
    expect(authDestination(null)).toBe("/login");
  });

  it("redirects an unauthenticated visitor away from a protected route", async () => {
    render(
      <AuthProvider>
        <AuthGate>
          <p>Private monitoring dashboard</p>
        </AuthGate>
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(routerReplace).toHaveBeenCalledWith("/login");
    });
    expect(
      screen.queryByText("Private monitoring dashboard"),
    ).not.toBeInTheDocument();
  });

  it("keeps a pending account out of protected dashboard content", async () => {
    const pendingUser = {
      ...activeOperator,
      role: "pending",
      is_active: false,
      approved_at: null,
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              access_token: "pending-token",
              token_type: "bearer",
              expires_in: 900,
            }),
            { status: 200 },
          ),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(pendingUser), { status: 200 }),
        ),
    );

    function PendingProtectedRoute() {
      const { signIn } = useAuth();
      return (
        <>
          <button
            onClick={() => void signIn("pending@example.com", "password")}
            type="button"
          >
            Sign in as pending
          </button>
          <AuthGate>
            <p>Private monitoring dashboard</p>
          </AuthGate>
        </>
      );
    }

    render(
      <AuthProvider>
        <PendingProtectedRoute />
      </AuthProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Sign in as pending" }));

    await waitFor(() => {
      expect(routerReplace).toHaveBeenCalledWith("/access-pending");
    });
    expect(
      screen.queryByText("Private monitoring dashboard"),
    ).not.toBeInTheDocument();
  });
});
