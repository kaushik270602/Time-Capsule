import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PasswordResetForm from "@/components/auth/PasswordResetForm";
import { authApi } from "@/lib/api";

// --- Mocks ---

jest.mock("@/lib/api", () => ({
  authApi: {
    requestPasswordReset: jest.fn(),
    resetPassword: jest.fn(),
  },
}));

jest.mock("next/link", () => {
  return ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  );
});

const mockRequestReset = authApi.requestPasswordReset as jest.Mock;
const mockResetPassword = authApi.resetPassword as jest.Mock;

// --- Tests ---

describe("PasswordResetForm - Request mode (no token)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders the request reset form", () => {
    render(<PasswordResetForm />);
    expect(screen.getByText(/reset your password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send reset link/i })).toBeInTheDocument();
  });

  it("shows error when email is empty", async () => {
    const user = userEvent.setup();
    render(<PasswordResetForm />);
    await user.click(screen.getByRole("button", { name: /send reset link/i }));
    expect(await screen.findByText(/email is required/i)).toBeInTheDocument();
    expect(mockRequestReset).not.toHaveBeenCalled();
  });

  it("calls requestPasswordReset and shows success on valid email", async () => {
    mockRequestReset.mockResolvedValueOnce({ data: { message: "ok" } });
    const user = userEvent.setup();
    render(<PasswordResetForm />);
    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.click(screen.getByRole("button", { name: /send reset link/i }));

    await waitFor(() => {
      expect(mockRequestReset).toHaveBeenCalledWith("test@example.com");
    });
    expect(await screen.findByText(/check your email/i)).toBeInTheDocument();
  });

  it("displays error on API failure", async () => {
    mockRequestReset.mockRejectedValueOnce({
      response: { data: { detail: "User not found" } },
    });
    const user = userEvent.setup();
    render(<PasswordResetForm />);
    await user.type(screen.getByLabelText(/email/i), "unknown@example.com");
    await user.click(screen.getByRole("button", { name: /send reset link/i }));

    expect(await screen.findByText(/user not found/i)).toBeInTheDocument();
  });
});

describe("PasswordResetForm - Reset mode (with token)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders the set new password form when token is provided", () => {
    render(<PasswordResetForm token="valid-token" />);
    expect(screen.getByText(/set new password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/new password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /update password/i })).toBeInTheDocument();
  });

  it("shows error when new password is too short", async () => {
    const user = userEvent.setup();
    render(<PasswordResetForm token="valid-token" />);
    await user.type(screen.getByLabelText(/new password/i), "Ab1");
    await user.type(screen.getByLabelText(/confirm password/i), "Ab1");
    await user.click(screen.getByRole("button", { name: /update password/i }));
    expect(await screen.findByText(/at least 8 characters/i)).toBeInTheDocument();
    expect(mockResetPassword).not.toHaveBeenCalled();
  });

  it("shows error when new password lacks complexity", async () => {
    const user = userEvent.setup();
    render(<PasswordResetForm token="valid-token" />);
    await user.type(screen.getByLabelText(/new password/i), "alllowercase");
    await user.type(screen.getByLabelText(/confirm password/i), "alllowercase");
    await user.click(screen.getByRole("button", { name: /update password/i }));
    expect(await screen.findByText(/uppercase, lowercase, and a number/i)).toBeInTheDocument();
  });

  it("shows error when passwords do not match", async () => {
    const user = userEvent.setup();
    render(<PasswordResetForm token="valid-token" />);
    await user.type(screen.getByLabelText(/new password/i), "ValidPass1");
    await user.type(screen.getByLabelText(/confirm password/i), "Different1");
    await user.click(screen.getByRole("button", { name: /update password/i }));
    expect(await screen.findByText(/passwords do not match/i)).toBeInTheDocument();
  });

  it("calls resetPassword and shows success on valid submission", async () => {
    mockResetPassword.mockResolvedValueOnce({ data: { message: "ok" } });
    const user = userEvent.setup();
    render(<PasswordResetForm token="valid-token" />);
    await user.type(screen.getByLabelText(/new password/i), "NewValidPass1");
    await user.type(screen.getByLabelText(/confirm password/i), "NewValidPass1");
    await user.click(screen.getByRole("button", { name: /update password/i }));

    await waitFor(() => {
      expect(mockResetPassword).toHaveBeenCalledWith("valid-token", "NewValidPass1");
    });
    expect(await screen.findByText(/password updated/i)).toBeInTheDocument();
  });

  it("displays error on API failure during reset", async () => {
    mockResetPassword.mockRejectedValueOnce({
      response: { data: { detail: "Token expired" } },
    });
    const user = userEvent.setup();
    render(<PasswordResetForm token="expired-token" />);
    await user.type(screen.getByLabelText(/new password/i), "NewValidPass1");
    await user.type(screen.getByLabelText(/confirm password/i), "NewValidPass1");
    await user.click(screen.getByRole("button", { name: /update password/i }));

    expect(await screen.findByText(/token expired/i)).toBeInTheDocument();
  });
});
