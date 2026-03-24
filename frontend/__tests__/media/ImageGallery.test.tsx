import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import ImageGallery from "@/components/media/ImageGallery";

describe("ImageGallery", () => {
  const sampleImages = [
    { src: "https://example.com/img1.jpg", alt: "First image" },
    { src: "https://example.com/img2.jpg", alt: "Second image" },
    { src: "https://example.com/img3.jpg", alt: "Third image" },
  ];

  it("renders nothing when images array is empty", () => {
    const { container } = render(<ImageGallery images={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders all images in a grid", () => {
    render(<ImageGallery images={sampleImages} />);
    const imgs = screen.getAllByRole("img");
    expect(imgs).toHaveLength(3);
    expect(imgs[0]).toHaveAttribute("src", "https://example.com/img1.jpg");
    expect(imgs[0]).toHaveAttribute("alt", "First image");
  });

  it("uses single column grid for one image", () => {
    render(<ImageGallery images={[sampleImages[0]]} />);
    const grid = screen.getByRole("img").closest(".grid");
    expect(grid?.className).toContain("grid-cols-1");
  });

  it("uses two column grid for two images", () => {
    render(<ImageGallery images={sampleImages.slice(0, 2)} />);
    const grid = screen.getAllByRole("img")[0].closest(".grid");
    expect(grid?.className).toContain("grid-cols-2");
  });

  it("opens lightbox when an image is clicked", () => {
    render(<ImageGallery images={sampleImages} />);
    const buttons = screen.getAllByRole("button", { name: /image/i });
    fireEvent.click(buttons[0]);

    // Lightbox should be open with dialog role
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("1 / 3")).toBeInTheDocument();
  });

  it("navigates to next and previous images in lightbox", () => {
    render(<ImageGallery images={sampleImages} />);
    const buttons = screen.getAllByRole("button", { name: /image/i });
    fireEvent.click(buttons[0]);

    // Go next
    fireEvent.click(screen.getByLabelText("Next image"));
    expect(screen.getByText("2 / 3")).toBeInTheDocument();

    // Go prev
    fireEvent.click(screen.getByLabelText("Previous image"));
    expect(screen.getByText("1 / 3")).toBeInTheDocument();
  });

  it("closes lightbox when close button is clicked", () => {
    render(<ImageGallery images={sampleImages} />);
    const buttons = screen.getAllByRole("button", { name: /image/i });
    fireEvent.click(buttons[0]);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Close lightbox"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes lightbox on Escape key", () => {
    render(<ImageGallery images={sampleImages} />);
    const buttons = screen.getAllByRole("button", { name: /image/i });
    fireEvent.click(buttons[0]);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows error placeholder when an image fails to load", () => {
    render(<ImageGallery images={sampleImages} />);
    const imgs = screen.getAllByRole("img");
    fireEvent.error(imgs[1]);

    expect(screen.getByText("Failed to load")).toBeInTheDocument();
  });

  it("wraps around when navigating past the last image", () => {
    render(<ImageGallery images={sampleImages} />);
    const buttons = screen.getAllByRole("button", { name: /image/i });
    fireEvent.click(buttons[2]); // Open on last image

    expect(screen.getByText("3 / 3")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Next image"));
    expect(screen.getByText("1 / 3")).toBeInTheDocument();
  });
});
