import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import NotificationsPage from "@/app/notifications/page";

// --- Mocks ---

jest.mock("next/link", () => {
  return ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
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

describe("NotificationsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders the page heading", async () => {
    mockList.mockResolvedValueOnce({ data: { notifications: [] } });
    render(<NotificationsPage />);
    await waitFor(() => {
      expect(screen.getByText("Notifications")).toBeInTheDocument();
    });
  });

  it("shows loading state initially", () => {
    mockList.mockReturnValue(new Promise(() => {})); // never resolves
    render(<NotificationsPage />);
    expect(screen.getByText(/loading notifications/i)).toBeInTheDocument();
  });

  it("shows error state when API fails", async () => {
    mockList.mockRejectedValueOnce(new Error("Network error"));
    render(<NotificationsPage />);
    await waitFor(() => {
      expect(screen.getByText(/failed to load notifications/i)).toBeInTheDocument();
    });
  });

  it("shows empty state when no notifications exist", async () => {
    mockList.mockResolvedValueOnce({ data: { notifications: [] } });
    render(<NotificationsPage />);
    await waitFor(() => {
      expect(screen.getByText(/no notifications yet/i)).toBeInTheDocument();
    });
    // Should have a link back to dashboard
    expect(screen.getByText(/back to dashboard/i).closest("a")).toHaveAttribute("href", "/dashboard");
  });

  it("displays notification list with messages", async () => {
    const notifications = [
      makeNotification({ id: 1, message: "Capsule Alpha unlocked!" }),
      makeNotification({ id: 2, message: "Capsule Beta unlocked!", is_read: true }),
    ];
    mockList.mockResolvedValueOnce({ data: { notifications } });
    render(<NotificationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Capsule Alpha unlocked!")).toBeInTheDocument();
    });
    expect(screen.getByText("Capsule Beta unlocked!")).toBeInTheDocument();
  });

  it("shows unread count in subtitle", async () => {
    const notifications = [
      makeNotification({ id: 1, is_read: false }),
      makeNotification({ id: 2, is_read: false }),
      makeNotification({ id: 3, is_read: true }),
    ];
    mockList.mockResolvedValueOnce({ data: { notifications } });
    render(<NotificationsPage />);

    await waitFor(() => {
      expect(screen.getByText("2 unread notifications")).toBeInTheDocument();
    });
  });

  it("shows 'All caught up!' when all are read", async () => {
    const notifications = [
      makeNotification({ id: 1, is_read: true }),
      makeNotification({ id: 2, is_read: true }),
    ];
    mockList.mockResolvedValueOnce({ data: { notifications } });
    render(<NotificationsPage />);

    await waitFor(() => {
      expect(screen.getByText("All caught up!")).toBeInTheDocument();
    });
  });

  it("marks individual notification as read on button click", async () => {
    const notifications = [
      makeNotification({ id: 7, message: "Time to open!", is_read: false }),
    ];
    mockList.mockResolvedValueOnce({ data: { notifications } });
    mockMarkRead.mockResolvedValueOnce({ data: { id: 7, is_read: true } });
    render(<NotificationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Time to open!")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Mark read"));

    await waitFor(() => {
      expect(mockMarkRead).toHaveBeenCalledWith(7);
    });
  });

  it("does not show 'Mark read' button for already-read notifications", async () => {
    const notifications = [
      makeNotification({ id: 1, is_read: true, message: "Already read" }),
    ];
    mockList.mockResolvedValueOnce({ data: { notifications } });
    render(<NotificationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Already read")).toBeInTheDocument();
    });
    expect(screen.queryByText("Mark read")).not.toBeInTheDocument();
  });

  it("links each notification to its capsule", async () => {
    const notifications = [
      makeNotification({ id: 1, capsule_id: 42 }),
    ];
    mockList.mockResolvedValueOnce({ data: { notifications } });
    render(<NotificationsPage />);

    await waitFor(() => {
      expect(screen.getByText("View capsule")).toBeInTheDocument();
    });
    expect(screen.getByText("View capsule").closest("a")).toHaveAttribute("href", "/capsules/42");
  });
});
