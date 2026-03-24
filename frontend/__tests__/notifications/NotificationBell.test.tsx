import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import NotificationBell from "@/components/notifications/NotificationBell";

// --- Mocks ---

jest.mock("next/link", () => {
  return ({ children, href, onClick }: { children: React.ReactNode; href: string; onClick?: () => void }) => (
    <a href={href} onClick={onClick}>{children}</a>
  );
});

const mockList = jest.fn();
const mockMarkRead = jest.fn();

jest.mock("@/lib/api", () => ({
  notificationApi: {
    list: (...args: unknown[]) => mockList(...args),
    markRead: (...args: unknown[]) => mockMarkRead(...args),
  },
}));

// --- Helpers ---

function makeNotification(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: 1,
    capsule_id: 10,
    message: "Your capsule has been unlocked!",
    is_read: false,
    created_at: "2024-06-15T12:00:00Z",
    ...overrides,
  };
}

// --- Tests ---

describe("NotificationBell", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders the bell icon button", async () => {
    mockList.mockResolvedValueOnce({ data: { notifications: [] } });
    render(<NotificationBell />);
    expect(screen.getByRole("button", { name: /notifications/i })).toBeInTheDocument();
  });

  it("shows unread count badge when there are unread notifications", async () => {
    const notifications = [
      makeNotification({ id: 1, is_read: false }),
      makeNotification({ id: 2, is_read: false }),
      makeNotification({ id: 3, is_read: true }),
    ];
    mockList.mockResolvedValueOnce({ data: { notifications } });
    render(<NotificationBell />);

    await waitFor(() => {
      expect(screen.getByText("2")).toBeInTheDocument();
    });
  });

  it("does not show badge when all notifications are read", async () => {
    const notifications = [
      makeNotification({ id: 1, is_read: true }),
      makeNotification({ id: 2, is_read: true }),
    ];
    mockList.mockResolvedValueOnce({ data: { notifications } });
    render(<NotificationBell />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Notifications" })).toBeInTheDocument();
    });
    // No badge should be present
    expect(screen.queryByText("2")).not.toBeInTheDocument();
  });

  it("opens dropdown on click and displays notifications", async () => {
    const notifications = [
      makeNotification({ id: 1, message: "Capsule Alpha unlocked!" }),
      makeNotification({ id: 2, message: "Capsule Beta unlocked!", is_read: true }),
    ];
    mockList.mockResolvedValueOnce({ data: { notifications } });
    render(<NotificationBell />);

    await waitFor(() => {
      expect(screen.getByText("1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /notifications/i }));

    expect(screen.getByText("Capsule Alpha unlocked!")).toBeInTheDocument();
    expect(screen.getByText("Capsule Beta unlocked!")).toBeInTheDocument();
    expect(screen.getByText("1 unread")).toBeInTheDocument();
  });

  it("marks a notification as read on click", async () => {
    const notifications = [
      makeNotification({ id: 5, message: "Time to open!", is_read: false }),
    ];
    mockList.mockResolvedValueOnce({ data: { notifications } });
    mockMarkRead.mockResolvedValueOnce({ data: { id: 5, is_read: true } });
    render(<NotificationBell />);

    await waitFor(() => {
      expect(screen.getByText("1")).toBeInTheDocument();
    });

    // Open dropdown
    fireEvent.click(screen.getByRole("button", { name: /notifications/i }));
    expect(screen.getByText("Time to open!")).toBeInTheDocument();

    // Click the notification to mark as read
    fireEvent.click(screen.getByRole("menuitem"));

    await waitFor(() => {
      expect(mockMarkRead).toHaveBeenCalledWith(5);
    });
  });

  it("shows 'View all notifications' link in dropdown", async () => {
    mockList.mockResolvedValueOnce({ data: { notifications: [makeNotification()] } });
    render(<NotificationBell />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /notifications/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /notifications/i }));

    const viewAllLink = screen.getByText("View all notifications");
    expect(viewAllLink).toBeInTheDocument();
    expect(viewAllLink.closest("a")).toHaveAttribute("href", "/notifications");
  });

  it("shows empty state when no notifications exist", async () => {
    mockList.mockResolvedValueOnce({ data: { notifications: [] } });
    render(<NotificationBell />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Notifications" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));

    expect(screen.getByText("No notifications yet")).toBeInTheDocument();
  });

  it("caps badge display at 99+", async () => {
    const notifications = Array.from({ length: 100 }, (_, i) =>
      makeNotification({ id: i + 1, is_read: false })
    );
    mockList.mockResolvedValueOnce({ data: { notifications } });
    render(<NotificationBell />);

    await waitFor(() => {
      expect(screen.getByText("99+")).toBeInTheDocument();
    });
  });
});
