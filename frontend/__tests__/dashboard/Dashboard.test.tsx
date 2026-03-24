import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import DashboardPage from "@/app/dashboard/page";
import StatsCards from "@/components/dashboard/StatsCards";
import Sidebar from "@/components/dashboard/Sidebar";

// --- Mocks ---

const mockPush = jest.fn();
const mockPathname = "/dashboard";

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => mockPathname,
}));

jest.mock("next/link", () => {
  return ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  );
});

const mockLogout = jest.fn();
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    user: { id: 1, email: "test@example.com", is_verified: true, created_at: "2024-01-01" },
    loading: false,
    logout: mockLogout,
  }),
}));

const mockList = jest.fn();
jest.mock("@/lib/api", () => ({
  capsuleApi: { list: () => mockList() },
}));

// --- StatsCards Tests ---

describe("StatsCards", () => {
  it("renders all three stat cards with correct values", () => {
    render(<StatsCards total={10} locked={6} unlocked={4} />);
    expect(screen.getByText("Total Capsules")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("Locked")).toBeInTheDocument();
    expect(screen.getByText("6")).toBeInTheDocument();
    expect(screen.getByText("Unlocked")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("shows loading skeleton when loading", () => {
    const { container } = render(<StatsCards total={0} locked={0} unlocked={0} loading />);
    const pulses = container.querySelectorAll(".animate-pulse");
    expect(pulses.length).toBe(3);
  });

  it("renders zero values correctly", () => {
    render(<StatsCards total={0} locked={0} unlocked={0} />);
    const zeros = screen.getAllByText("0");
    expect(zeros.length).toBe(3);
  });
});

// --- Sidebar Tests ---

describe("Sidebar", () => {
  it("renders navigation links", () => {
    render(<Sidebar />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Create Capsule")).toBeInTheDocument();
    expect(screen.getByText("Public Feed")).toBeInTheDocument();
    expect(screen.getByText("Notifications")).toBeInTheDocument();
  });

  it("renders the TimeLock brand", () => {
    render(<Sidebar />);
    expect(screen.getByText("TimeLock")).toBeInTheDocument();
  });

  it("displays user email", () => {
    render(<Sidebar />);
    expect(screen.getByText("test@example.com")).toBeInTheDocument();
  });

  it("renders sign out button", () => {
    render(<Sidebar />);
    expect(screen.getByText("Sign Out")).toBeInTheDocument();
  });
});

// --- DashboardPage Tests ---

describe("DashboardPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders dashboard heading", async () => {
    mockList.mockResolvedValueOnce({ data: [] });
    render(<DashboardPage />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("shows empty state when no capsules exist", async () => {
    mockList.mockResolvedValueOnce({ data: [] });
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText(/haven't created any capsules/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/create your first capsule/i)).toBeInTheDocument();
  });

  it("displays capsules and correct stats after loading", async () => {
    const capsules = [
      { id: 1, title: "My Locked Capsule", status: "locked", unlock_date: "2030-01-01T00:00:00Z", is_public: false, created_at: "2024-01-01", text_content: null, media_urls: [], transcriptions: [], time_until_unlock: 999, user_id: 1 },
      { id: 2, title: "My Unlocked Capsule", status: "unlocked", unlock_date: "2024-01-01T00:00:00Z", is_public: true, created_at: "2023-01-01", text_content: "hello", media_urls: [], transcriptions: [], time_until_unlock: null, user_id: 1 },
    ];
    mockList.mockResolvedValueOnce({ data: capsules });
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("My Locked Capsule")).toBeInTheDocument();
    });
    expect(screen.getByText("My Unlocked Capsule")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument(); // total
  });

  it("shows error message when API call fails", async () => {
    mockList.mockRejectedValueOnce(new Error("Network error"));
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText(/failed to load capsules/i)).toBeInTheDocument();
    });
  });
});

// --- Dashboard Filter & Search Integration Tests ---

describe("DashboardPage - Filters and Search", () => {
  const capsules = [
    { id: 1, title: "Summer Memories", status: "locked", unlock_date: "2030-06-15T12:00:00Z", is_public: false, created_at: "2024-01-01", text_content: null, media_urls: [], transcriptions: [], time_until_unlock: 999, user_id: 1 },
    { id: 2, title: "Winter Notes", status: "unlocked", unlock_date: "2024-01-01T00:00:00Z", is_public: true, created_at: "2023-01-01", text_content: "snowfall in december", media_urls: [], transcriptions: [], time_until_unlock: null, user_id: 1 },
    { id: 3, title: "Birthday Wish", status: "locked", unlock_date: "2031-03-20T00:00:00Z", is_public: false, created_at: "2024-02-01", text_content: "happy birthday future me", media_urls: [], transcriptions: [], time_until_unlock: 999, user_id: 1 },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders FilterBar after loading", async () => {
    mockList.mockResolvedValueOnce({ data: capsules });
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search by title or content/i)).toBeInTheDocument();
    });
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });

  it("filters capsules by locked status", async () => {
    mockList.mockResolvedValueOnce({ data: capsules });
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("Summer Memories")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "locked" } });

    expect(screen.getByText("Summer Memories")).toBeInTheDocument();
    expect(screen.getByText("Birthday Wish")).toBeInTheDocument();
    expect(screen.queryByText("Winter Notes")).not.toBeInTheDocument();
  });

  it("filters capsules by unlocked status", async () => {
    mockList.mockResolvedValueOnce({ data: capsules });
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("Winter Notes")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "unlocked" } });

    expect(screen.getByText("Winter Notes")).toBeInTheDocument();
    expect(screen.queryByText("Summer Memories")).not.toBeInTheDocument();
    expect(screen.queryByText("Birthday Wish")).not.toBeInTheDocument();
  });

  it("searches capsules by title (case-insensitive)", async () => {
    mockList.mockResolvedValueOnce({ data: capsules });
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("Summer Memories")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/search by title or content/i), {
      target: { value: "birthday" },
    });

    expect(screen.getByText("Birthday Wish")).toBeInTheDocument();
    expect(screen.queryByText("Summer Memories")).not.toBeInTheDocument();
    expect(screen.queryByText("Winter Notes")).not.toBeInTheDocument();
  });

  it("searches capsules by text_content (case-insensitive)", async () => {
    mockList.mockResolvedValueOnce({ data: capsules });
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("Winter Notes")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/search by title or content/i), {
      target: { value: "SNOWFALL" },
    });

    expect(screen.getByText("Winter Notes")).toBeInTheDocument();
    expect(screen.queryByText("Summer Memories")).not.toBeInTheDocument();
  });

  it("combines status filter and search", async () => {
    mockList.mockResolvedValueOnce({ data: capsules });
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("Summer Memories")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "locked" } });
    fireEvent.change(screen.getByPlaceholderText(/search by title or content/i), {
      target: { value: "birthday" },
    });

    expect(screen.getByText("Birthday Wish")).toBeInTheDocument();
    expect(screen.queryByText("Summer Memories")).not.toBeInTheDocument();
    expect(screen.queryByText("Winter Notes")).not.toBeInTheDocument();
  });

  it("shows all capsules when filter is reset to all", async () => {
    mockList.mockResolvedValueOnce({ data: capsules });
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("Summer Memories")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "locked" } });
    expect(screen.queryByText("Winter Notes")).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "all" } });
    expect(screen.getByText("Winter Notes")).toBeInTheDocument();
    expect(screen.getByText("Summer Memories")).toBeInTheDocument();
  });
});
