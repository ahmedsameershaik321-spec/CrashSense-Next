import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AdminUsersPanel } from "@/components/admin-users-panel";
import { DashboardShell } from "@/components/dashboard-shell";
import AdminPage from "@/app/dashboard/admin/page";
import { ApiError, type AdminUser } from "@/lib/api";

const mocks = vi.hoisted(() => ({
  approveAdminUser: vi.fn(),
  listAdminUsers: vi.fn(),
  updateAdminUserRole: vi.fn(),
  updateAdminUserStatus: vi.fn(),
  replace: vi.fn(),
  session: null as null | {
    accessToken: string;
    user: {
      id: string;
      email: string;
      first_name: string;
      last_name: string | null;
      role: string;
      is_active: boolean;
      is_email_verified: boolean;
      approved_at: string | null;
      created_at: string;
    };
  },
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    approveAdminUser: mocks.approveAdminUser,
    listAdminUsers: mocks.listAdminUsers,
    updateAdminUserRole: mocks.updateAdminUserRole,
    updateAdminUserStatus: mocks.updateAdminUserStatus,
  };
});

vi.mock("@/components/auth-provider", () => ({
  useAuth: () => ({
    session: mocks.session,
    signOut: vi.fn(),
  }),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/admin",
  useRouter: () => ({ replace: mocks.replace }),
}));

const currentAdmin: AdminUser = {
  id: "admin-1",
  email: "admin@example.test",
  first_name: "Admin",
  last_name: "User",
  role: "administrator",
  is_active: true,
  is_email_verified: true,
  approved_at: null,
  created_at: "2026-10-30T12:00:00Z",
};
const pendingUser: AdminUser = {
  id: "pending-1",
  email: "pending@example.test",
  first_name: "Pending",
  last_name: "Account",
  role: "pending",
  is_active: false,
  is_email_verified: false,
  approved_at: null,
  created_at: "2026-10-30T12:00:00Z",
};
const operatorUser: AdminUser = {
  ...pendingUser,
  id: "operator-1",
  email: "operator@example.test",
  role: "monitoring_operator",
  is_active: true,
  approved_at: "2026-10-30T12:00:00Z",
};

beforeEach(() => {
  mocks.approveAdminUser.mockReset();
  mocks.listAdminUsers.mockReset();
  mocks.updateAdminUserRole.mockReset();
  mocks.updateAdminUserStatus.mockReset();
  mocks.replace.mockReset();
  mocks.session = null;
  vi.stubGlobal("confirm", vi.fn(() => true));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("administrator user management", () => {
  it("approves a pending registration with the selected authorized role", async () => {
    mocks.listAdminUsers.mockResolvedValue([pendingUser]);
    mocks.approveAdminUser.mockResolvedValue({
      ...pendingUser,
      role: "administrator",
      is_active: true,
      approved_at: "2026-10-31T12:00:00Z",
    });
    render(
      <AdminUsersPanel accessToken="admin-token" currentUserId={currentAdmin.id} />,
    );

    await screen.findByText("pending@example.test");
    fireEvent.change(
      screen.getByRole("combobox", {
        name: "Role for pending@example.test",
      }),
      { target: { value: "administrator" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => {
      expect(mocks.approveAdminUser).toHaveBeenCalledWith(
        "admin-token",
        pendingUser.id,
        "administrator",
      );
    });
    expect(await screen.findByText("pending@example.test account was updated.")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("updates an approved user's role and suspension state", async () => {
    mocks.listAdminUsers.mockResolvedValue([operatorUser]);
    mocks.updateAdminUserRole.mockResolvedValue({
      ...operatorUser,
      role: "administrator",
    });
    mocks.updateAdminUserStatus.mockResolvedValue({
      ...operatorUser,
      is_active: false,
    });
    render(
      <AdminUsersPanel accessToken="admin-token" currentUserId={currentAdmin.id} />,
    );

    await screen.findByText("operator@example.test");
    fireEvent.change(
      screen.getByRole("combobox", {
        name: "Role for operator@example.test",
      }),
      { target: { value: "administrator" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Save role" }));
    await waitFor(() => {
      expect(mocks.updateAdminUserRole).toHaveBeenCalledWith(
        "admin-token",
        operatorUser.id,
        "administrator",
      );
    });

    fireEvent.click(await screen.findByRole("button", { name: "Suspend" }));
    await waitFor(() => {
      expect(mocks.updateAdminUserStatus).toHaveBeenCalledWith(
        "admin-token",
        operatorUser.id,
        false,
      );
    });
    expect(await screen.findByText("Suspended")).toBeInTheDocument();
  });

  it("shows API authorization errors and can retry", async () => {
    mocks.listAdminUsers
      .mockRejectedValueOnce(new ApiError("Administrator access is required.", 403))
      .mockResolvedValueOnce([]);
    render(
      <AdminUsersPanel accessToken="operator-token" currentUserId="operator-id" />,
    );
    expect(
      await screen.findByText(
        "Administrator access is required to manage users.",
      ),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("No registered accounts were returned by the API.")).toBeInTheDocument();
    expect(mocks.listAdminUsers).toHaveBeenCalledTimes(2);
  });

  it("paginates using the backend's bounded offset API", async () => {
    const firstPage = Array.from({ length: 20 }, (_, index) => ({
      ...operatorUser,
      id: `user-${index}`,
      email: `user-${index}@example.test`,
    }));
    mocks.listAdminUsers
      .mockResolvedValueOnce(firstPage)
      .mockResolvedValueOnce([]);
    render(
      <AdminUsersPanel accessToken="admin-token" currentUserId={currentAdmin.id} />,
    );
    await screen.findByText("user-0@example.test");
    fireEvent.click(screen.getByRole("button", { name: "Next user page" }));
    await waitFor(() => {
      expect(mocks.listAdminUsers).toHaveBeenLastCalledWith(
        "admin-token",
        20,
        20,
      );
    });
    expect(
      await screen.findByText("There are no more account records."),
    ).toBeInTheDocument();
  });
});

describe("administrator route and navigation", () => {
  it("redirects non-administrators and does not request admin data", async () => {
    mocks.session = {
      accessToken: "operator-token",
      user: {
        ...operatorUser,
      },
    };
    render(<AdminPage />);

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/dashboard"));
    expect(mocks.listAdminUsers).not.toHaveBeenCalled();
  });

  it("shows the administrator navigation only to administrators", () => {
    mocks.session = {
      accessToken: "admin-token",
      user: currentAdmin,
    };
    const { rerender } = render(
      <DashboardShell>
        <div>Page</div>
      </DashboardShell>,
    );
    expect(screen.getByRole("link", { name: "User management" })).toHaveAttribute(
      "href",
      "/dashboard/admin",
    );

    mocks.session = {
      accessToken: "operator-token",
      user: { ...currentAdmin, role: "monitoring_operator" },
    };
    rerender(
      <DashboardShell>
        <div>Page</div>
      </DashboardShell>,
    );
    expect(screen.queryByRole("link", { name: "User management" })).not.toBeInTheDocument();
  });
});
