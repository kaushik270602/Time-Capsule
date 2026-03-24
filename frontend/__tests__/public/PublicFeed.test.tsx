import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import PublicFeedPage from "@/app/public/page";

// --- Mocks ---

jest.mock("next/link", () => {
  return ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  );
});

const mockPublicFeed = jest.fn();
jest.mock("@/lib/api", () => ({
  capsuleApi: { publicFeed: (...args: unknown[]) => mockPublicFeed(...args) },
}));

// --- Helpers ---

function makeCapsule(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: 1,
    title: "Public Capsule",
    text_content: "Hello from the past!",
    unlock_date: "2024-06-15T12:00:00Z",
    created_at: "2024-01-01T00:00:00Z",
    user_id: 42,
    ...overrides,
  };
}

// --- Tests ---

describe("PublicFeedPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders page heading and description", async () => {
    mockPublicFeed.mockResolvedValueOnce({ data: { capsules: [], total: 0 } });
    render(<PublicFeedPage />);
    expect(screen.getByText("Public Feed")).toBeInTheDocument();
    expect(screen.getByText(/recently unlocked time capsules/i)).toBeInTheDocument();
  });

  it("shows loading skeleton while fetching", () => {
    mockPublicFeed.mockReturnValue(new Promise(() => {})); // never resolves
    render(<PublicFeedPage />);
    expect(screen.getByTestId("loading-skeleton")).toBeInTheDocument();
  });

  it("shows empty state when no capsules returned", async () => {
    mockPublicFeed.mockResolvedValueOnce({ data: { capsules: [], total: 0 } });
    render(<PublicFeedPage />);
    await waitFor(() => {
      expect(screen.getByText(/no public capsules yet/i)).toBeInTheDocument();
    });
  });

  it("displays capsule title, creator, unlock date, and preview", async () => {
    const capsule = makeCapsule();
    mockPublicFeed.mockResolvedValueOnce({
      data: { capsules: [capsule], total: 1 },
    });
    render(<PublicFeedPage />);

    await waitFor(() => {
      expect(screen.getByText("Public Capsule")).toBeInTheDocument();
    });
    expect(screen.getByText(/User #42/)).toBeInTheDocument();
    expect(screen.getByText(/Unlocked/)).toBeInTheDocument();
    expect(screen.getByText("Hello from the past!")).toBeInTheDocument();
  });

  it("truncates long text content preview", async () => {
    const longText = "A".repeat(200);
    const capsule = makeCapsule({ text_content: longText });
    mockPublicFeed.mockResolvedValueOnce({
      data: { capsules: [capsule], total: 1 },
    });
    render(<PublicFeedPage />);

    await waitFor(() => {
      expect(screen.getByText("Public Capsule")).toBeInTheDocument();
    });
    // Should be truncated with ellipsis
    const preview = screen.getByText(/A+…$/);
    expect(preview.textContent!.length).toBeLessThan(200);
  });

  it("links each capsule to its detail view", async () => {
    const capsule = makeCapsule({ id: 7 });
    mockPublicFeed.mockResolvedValueOnce({
      data: { capsules: [capsule], total: 1 },
    });
    render(<PublicFeedPage />);

    await waitFor(() => {
      expect(screen.getByText("Public Capsule")).toBeInTheDocument();
    });
    const link = screen.getByText("Public Capsule").closest("a");
    expect(link).toHaveAttribute("href", "/capsules/7");
  });

  it("shows error message when API call fails", async () => {
    mockPublicFeed.mockRejectedValueOnce(new Error("Network error"));
    render(<PublicFeedPage />);
    await waitFor(() => {
      expect(screen.getByText(/failed to load public capsules/i)).toBeInTheDocument();
    });
  });

  it("does not require authentication (no auth redirect)", async () => {
    mockPublicFeed.mockResolvedValueOnce({ data: { capsules: [], total: 0 } });
    render(<PublicFeedPage />);
    await waitFor(() => {
      expect(screen.getByText(/no public capsules yet/i)).toBeInTheDocument();
    });
    // Sign In and Sign Up links should be visible (not redirected)
    expect(screen.getByText("Sign In")).toBeInTheDocument();
    expect(screen.getByText("Sign Up")).toBeInTheDocument();
  });

  it("renders navigation links to login and register", async () => {
    mockPublicFeed.mockResolvedValueOnce({ data: { capsules: [], total: 0 } });
    render(<PublicFeedPage />);
    await waitFor(() => {
      expect(screen.getByText("Sign In")).toBeInTheDocument();
    });
    expect(screen.getByText("Sign In").closest("a")).toHaveAttribute("href", "/login");
    expect(screen.getByText("Sign Up").closest("a")).toHaveAttribute("href", "/register");
  });
});

describe("PublicFeedPage - Pagination", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("shows Load More button when a full page is returned", async () => {
    const capsules = Array.from({ length: 20 }, (_, i) =>
      makeCapsule({ id: i + 1, title: `Capsule ${i + 1}` })
    );
    mockPublicFeed.mockResolvedValueOnce({
      data: { capsules, total: 20 },
    });
    render(<PublicFeedPage />);

    await waitFor(() => {
      expect(screen.getByText("Capsule 1")).toBeInTheDocument();
    });
    expect(screen.getByText("Load More")).toBeInTheDocument();
  });

  it("hides Load More button when fewer than PAGE_SIZE capsules returned", async () => {
    const capsules = [makeCapsule()];
    mockPublicFeed.mockResolvedValueOnce({
      data: { capsules, total: 1 },
    });
    render(<PublicFeedPage />);

    await waitFor(() => {
      expect(screen.getByText("Public Capsule")).toBeInTheDocument();
    });
    expect(screen.queryByText("Load More")).not.toBeInTheDocument();
  });

  it("loads more capsules when Load More is clicked", async () => {
    const page1 = Array.from({ length: 20 }, (_, i) =>
      makeCapsule({ id: i + 1, title: `Page1 Capsule ${i + 1}` })
    );
    const page2 = [makeCapsule({ id: 21, title: "Page2 Capsule" })];

    mockPublicFeed.mockResolvedValueOnce({
      data: { capsules: page1, total: 20 },
    });
    render(<PublicFeedPage />);

    await waitFor(() => {
      expect(screen.getByText("Page1 Capsule 1")).toBeInTheDocument();
    });

    mockPublicFeed.mockResolvedValueOnce({
      data: { capsules: page2, total: 1 },
    });
    fireEvent.click(screen.getByText("Load More"));

    await waitFor(() => {
      expect(screen.getByText("Page2 Capsule")).toBeInTheDocument();
    });
    // Original capsules still visible
    expect(screen.getByText("Page1 Capsule 1")).toBeInTheDocument();
    // Load More hidden since page2 had < 20 items
    expect(screen.queryByText("Load More")).not.toBeInTheDocument();
  });

  it("passes correct offset to API on Load More", async () => {
    const page1 = Array.from({ length: 20 }, (_, i) =>
      makeCapsule({ id: i + 1, title: `C${i + 1}` })
    );
    mockPublicFeed.mockResolvedValueOnce({
      data: { capsules: page1, total: 20 },
    });
    render(<PublicFeedPage />);

    await waitFor(() => {
      expect(screen.getByText("C1")).toBeInTheDocument();
    });

    mockPublicFeed.mockResolvedValueOnce({
      data: { capsules: [], total: 0 },
    });
    fireEvent.click(screen.getByText("Load More"));

    await waitFor(() => {
      expect(mockPublicFeed).toHaveBeenCalledTimes(2);
    });
    // First call: offset 0, second call: offset 20
    expect(mockPublicFeed).toHaveBeenNthCalledWith(1, 20, 0);
    expect(mockPublicFeed).toHaveBeenNthCalledWith(2, 20, 20);
  });
});
