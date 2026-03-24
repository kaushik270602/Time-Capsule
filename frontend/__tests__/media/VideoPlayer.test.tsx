import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import VideoPlayer from "@/components/media/VideoPlayer";

describe("VideoPlayer", () => {
  it("renders a video element with the provided src", () => {
    render(<VideoPlayer src="https://example.com/video.mp4" />);
    const video = document.querySelector("video") as HTMLVideoElement;
    expect(video).toBeInTheDocument();
    expect(video.src).toBe("https://example.com/video.mp4");
    expect(video).toHaveAttribute("controls");
  });

  it("shows loading state initially", () => {
    render(<VideoPlayer src="https://example.com/video.mp4" />);
    expect(screen.getByText("Loading video…")).toBeInTheDocument();
  });

  it("hides loading state after video loads", () => {
    render(<VideoPlayer src="https://example.com/video.mp4" />);
    const video = document.querySelector("video") as HTMLVideoElement;
    fireEvent.loadedData(video);
    expect(screen.queryByText("Loading video…")).not.toBeInTheDocument();
  });

  it("shows error state with download link when video fails to load", () => {
    render(<VideoPlayer src="https://example.com/video.mp4" />);
    const video = document.querySelector("video") as HTMLVideoElement;
    fireEvent.error(video);

    expect(screen.getByText("Unable to load video")).toBeInTheDocument();
    const downloadLink = screen.getByText("Download video file");
    expect(downloadLink).toHaveAttribute("href", "https://example.com/video.mp4");
  });

  it("does not render transcription when not provided", () => {
    render(<VideoPlayer src="https://example.com/video.mp4" />);
    expect(screen.queryByText("Transcription")).not.toBeInTheDocument();
  });

  it("renders transcription text below the video when provided", () => {
    render(
      <VideoPlayer
        src="https://example.com/video.mp4"
        transcription="Hello, this is a test transcription."
      />
    );
    expect(screen.getByText("Transcription")).toBeInTheDocument();
    expect(screen.getByText("Hello, this is a test transcription.")).toBeInTheDocument();
  });

  it("shows transcription even in error state", () => {
    render(
      <VideoPlayer
        src="https://example.com/bad.mp4"
        transcription="Some transcription text"
      />
    );
    const video = document.querySelector("video") as HTMLVideoElement;
    fireEvent.error(video);

    expect(screen.getByText("Unable to load video")).toBeInTheDocument();
    expect(screen.getByText("Transcription")).toBeInTheDocument();
    expect(screen.getByText("Some transcription text")).toBeInTheDocument();
  });

  it("truncates long transcriptions with show more/less toggle", () => {
    const longText = "A".repeat(400);
    render(
      <VideoPlayer src="https://example.com/video.mp4" transcription={longText} />
    );

    // Should be truncated
    expect(screen.getByText(/^A+…$/)).toBeInTheDocument();
    expect(screen.getByText("Show more")).toBeInTheDocument();

    // Expand
    fireEvent.click(screen.getByText("Show more"));
    expect(screen.getByText(longText)).toBeInTheDocument();
    expect(screen.getByText("Show less")).toBeInTheDocument();
  });
});
