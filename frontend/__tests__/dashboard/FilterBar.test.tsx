import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import FilterBar, { StatusFilter } from "@/components/dashboard/FilterBar";

function renderFilterBar(overrides: Partial<{
  statusFilter: StatusFilter;
  searchQuery: string;
  onStatusChange: (s: StatusFilter) => void;
  onSearchChange: (q: string) => void;
}> = {}) {
  const props = {
    statusFilter: "all" as StatusFilter,
    searchQuery: "",
    onStatusChange: jest.fn(),
    onSearchChange: jest.fn(),
    ...overrides,
  };
  const result = render(<FilterBar {...props} />);
  return { ...result, ...props };
}

describe("FilterBar", () => {
  it("renders search input and status dropdown", () => {
    renderFilterBar();
    expect(screen.getByPlaceholderText(/search by title or content/i)).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });

  it("displays all status options", () => {
    renderFilterBar();
    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(3);
    expect(options[0]).toHaveTextContent("All");
    expect(options[1]).toHaveTextContent("Locked");
    expect(options[2]).toHaveTextContent("Unlocked");
  });

  it("calls onStatusChange when status filter changes", () => {
    const onStatusChange = jest.fn();
    renderFilterBar({ onStatusChange });
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "locked" } });
    expect(onStatusChange).toHaveBeenCalledWith("locked");
  });

  it("calls onSearchChange when search input changes", () => {
    const onSearchChange = jest.fn();
    renderFilterBar({ onSearchChange });
    fireEvent.change(screen.getByPlaceholderText(/search by title or content/i), {
      target: { value: "hello" },
    });
    expect(onSearchChange).toHaveBeenCalledWith("hello");
  });

  it("reflects current statusFilter value", () => {
    renderFilterBar({ statusFilter: "locked" });
    expect(screen.getByRole("combobox")).toHaveValue("locked");
  });

  it("reflects current searchQuery value", () => {
    renderFilterBar({ searchQuery: "my capsule" });
    expect(screen.getByPlaceholderText(/search by title or content/i)).toHaveValue("my capsule");
  });

  it("has accessible labels for search and filter", () => {
    renderFilterBar();
    expect(screen.getByLabelText(/search capsules/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/filter by status/i)).toBeInTheDocument();
  });
});
