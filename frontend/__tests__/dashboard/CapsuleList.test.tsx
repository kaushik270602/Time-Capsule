import React from "react";
import { render, screen } from "@testing-library/react";
import CapsuleCard from "@/components/dashboard/CapsuleCard";
import CapsuleList from "@/components/dashboard/CapsuleList";
import { CapsuleResponse } from "@/lib/api";

jest.mock("next/link", () => {
  return ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  );
});

function makeCapsule(overrides: Partial<CapsuleResponse> = {}): CapsuleResponse {
  return {
    id: 1,
    title: "Test Capsule",
    text_content: null,
    media_urls: [],
    transcriptions: [],
    unlock_date: "2030-06-15T12:00:00Z",
    status: "locked",
    is_public: false,
    created_at: "2024-01-01T00:00:00Z",
    time_until_unlock: 999999,
    user_id: 1,
    ...overrides,
  };
}

// --- CapsuleCard Tests ---

describe("CapsuleCard", () => {
  it("renders capsule title and links to detail page", () => {
    const capsule = makeCapsule({ id: 42, title: "My Memory" });
    render(<CapsuleCard capsule={capsule} />);
    expect(screen.getByText("My Memory")).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute("href", "/capsules/42");
  });

  it("shows locked status badge for locked capsule", () => {
    render(<CapsuleCard capsule={makeCapsule({ status: "locked" })} />);
    expect(screen.getByText("locked")).toBeInTheDocument();
  });

  it("shows unlocked status badge for unlocked capsule", () => {
    render(
      <CapsuleCard
        capsule={makeCapsule({ status: "unlocked", time_until_unlock: null })}
      />
    );
    expect(screen.getByText("unlocked")).toBeInTheDocument();
  });

  it("shows countdown timer for locked capsule", () => {
    render(<CapsuleCard capsule={makeCapsule({ status: "locked" })} />);
    expect(screen.getByText(/\d+[dhm]/)).toBeInTheDocument();
  });

  it("does not show countdown for unlocked capsule", () => {
    render(
      <CapsuleCard
        capsule={makeCapsule({ status: "unlocked", time_until_unlock: null })}
      />
    );
    expect(screen.queryByText("⏳")).not.toBeInTheDocument();
  });

  it("shows Public badge when capsule is public", () => {
    render(<CapsuleCard capsule={makeCapsule({ is_public: true })} />);
    expect(screen.getByText("Public")).toBeInTheDocument();
  });

  it("shows Private badge when capsule is private", () => {
    render(<CapsuleCard capsule={makeCapsule({ is_public: false })} />);
    expect(screen.getByText("Private")).toBeInTheDocument();
  });
});

// --- CapsuleList Tests ---

describe("CapsuleList", () => {
  it("shows empty state when no capsules", () => {
    render(<CapsuleList capsules={[]} />);
    expect(screen.getByText(/haven't created any capsules/i)).toBeInTheDocument();
    expect(screen.getByText(/create your first capsule/i)).toBeInTheDocument();
  });

  it("separates locked and unlocked capsules into sections", () => {
    const capsules = [
      makeCapsule({ id: 1, title: "Locked One", status: "locked" }),
      makeCapsule({ id: 2, title: "Unlocked One", status: "unlocked", time_until_unlock: null }),
    ];
    render(<CapsuleList capsules={capsules} />);
    expect(screen.getByText("Locked Capsules")).toBeInTheDocument();
    expect(screen.getByText("Unlocked Capsules")).toBeInTheDocument();
    expect(screen.getByText("Locked One")).toBeInTheDocument();
    expect(screen.getByText("Unlocked One")).toBeInTheDocument();
  });

  it("shows section counts", () => {
    const capsules = [
      makeCapsule({ id: 1, status: "locked" }),
      makeCapsule({ id: 2, status: "locked" }),
      makeCapsule({ id: 3, status: "unlocked", time_until_unlock: null }),
    ];
    render(<CapsuleList capsules={capsules} />);
    expect(screen.getByText("(2)")).toBeInTheDocument();
    expect(screen.getByText("(1)")).toBeInTheDocument();
  });

  it("hides locked section when no locked capsules", () => {
    const capsules = [
      makeCapsule({ id: 1, status: "unlocked", time_until_unlock: null }),
    ];
    render(<CapsuleList capsules={capsules} />);
    expect(screen.queryByText("Locked Capsules")).not.toBeInTheDocument();
    expect(screen.getByText("Unlocked Capsules")).toBeInTheDocument();
  });

  it("hides unlocked section when no unlocked capsules", () => {
    const capsules = [makeCapsule({ id: 1, status: "locked" })];
    render(<CapsuleList capsules={capsules} />);
    expect(screen.getByText("Locked Capsules")).toBeInTheDocument();
    expect(screen.queryByText("Unlocked Capsules")).not.toBeInTheDocument();
  });
});
