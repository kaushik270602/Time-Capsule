import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import AudioPlayer from "@/components/media/AudioPlayer";

describe("AudioPlayer", () => {
  it("renders an audio element with the provided src", () => {
    render(<AudioPlayer src="https://example.com/audio.mp3" />);
    const audio = document.querySelector("audio") as HTMLAudioElement;
    expect(audio).toBeInTheDocument();
    expect(audio.src).toBe("https://example.com/audio.mp3");
    expect(audio).toHaveAttribute("controls");
  });

  it("shows loading state initially", () => {
    render(<AudioPlayer src="https://example.com/audio.mp3" />);
    expect(screen.getByText("Loading audio…")).toBeInTheDocument();
  });

  it("hides loading state after audio loads", () => {
    render(<AudioPlayer src="https://example.com/audio.mp3" />);
    const audio = document.querySelector("audio") as HTMLAudioElement;
    fireEvent.loadedData(audio);
    expect(screen.queryByText("Loading audio…")).not.toBeInTheDocument();
  });

  it("shows error state with download link when audio fails to load", () => {
    render(<AudioPlayer src="https://example.com/audio.mp3" />);
    const audio = document.querySelector("audio") as HTMLAudioElement;
    fireEvent.error(audio);

    expect(screen.getByText("Unable to load audio")).toBeInTheDocument();
    const downloadLink = screen.getByText("Download audio file");
    expect(downloadLink).toHaveAttribute("href", "https://example.com/audio.mp3");
  });

  it("does not render transcription when not provided", () => {
    render(<AudioPlayer src="https://example.com/audio.mp3" />);
    expect(screen.queryByText("Transcription")).not.toBeInTheDocument();
  });

  it("renders transcription text below the audio when provided", () => {
    render(
      <AudioPlayer
        src="https://example.com/audio.mp3"
        transcription="This is the audio transcription."
      />
    );
    expect(screen.getByText("Transcription")).toBeInTheDocument();
    expect(screen.getByText("This is the audio transcription.")).toBeInTheDocument();
  });

  it("shows transcription even in error state", () => {
    render(
      <AudioPlayer
        src="https://example.com/bad.mp3"
        transcription="Transcription for broken audio"
      />
    );
    const audio = document.querySelector("audio") as HTMLAudioElement;
    fireEvent.error(audio);

    expect(screen.getByText("Unable to load audio")).toBeInTheDocument();
    expect(screen.getByText("Transcription")).toBeInTheDocument();
  });

  it("truncates long transcriptions with show more/less toggle", () => {
    const longText = "B".repeat(400);
    render(
      <AudioPlayer src="https://example.com/audio.mp3" transcription={longText} />
    );

    expect(screen.getByText(/^B+…$/)).toBeInTheDocument();
    expect(screen.getByText("Show more")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Show more"));
    expect(screen.getByText(longText)).toBeInTheDocument();
    expect(screen.getByText("Show less")).toBeInTheDocument();
  });
});
