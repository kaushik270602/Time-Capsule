import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MediaUploader, { PendingFile } from "@/components/capsule/MediaUploader";

// Helper to create a mock File
function createMockFile(
  name: string,
  size: number,
  type: string
): File {
  const buffer = new ArrayBuffer(size);
  return new File([buffer], name, { type });
}

describe("MediaUploader", () => {
  const defaultProps = {
    mediaType: "image" as const,
    files: [] as PendingFile[],
    onChange: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    // Mock URL.createObjectURL
    global.URL.createObjectURL = jest.fn(() => "blob:mock-url");
    global.URL.revokeObjectURL = jest.fn();
  });

  it("renders the drop zone with correct label for each media type", () => {
    const { rerender } = render(<MediaUploader {...defaultProps} mediaType="video" />);
    expect(screen.getByText(/video/i, { selector: "label" })).toBeInTheDocument();

    rerender(<MediaUploader {...defaultProps} mediaType="audio" />);
    expect(screen.getByText(/audio/i, { selector: "label" })).toBeInTheDocument();

    rerender(<MediaUploader {...defaultProps} mediaType="image" />);
    expect(screen.getByText(/images/i, { selector: "label" })).toBeInTheDocument();
  });

  it("shows accepted formats and max size in the drop zone", () => {
    render(<MediaUploader {...defaultProps} mediaType="video" />);
    expect(screen.getByText(/\.mp4,.mov,.avi/i)).toBeInTheDocument();
    expect(screen.getByText(/500\.0 MB/)).toBeInTheDocument();
  });

  // --- File validation tests ---

  it("validates image file format and rejects unsupported types", async () => {
    const onChange = jest.fn();
    render(<MediaUploader {...defaultProps} onChange={onChange} mediaType="image" />);

    const badFile = createMockFile("doc.pdf", 1024, "application/pdf");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    // Manually set files and fire change since userEvent.upload respects accept attribute
    Object.defineProperty(input, "files", { value: [badFile], configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));

    await waitFor(() => {
      expect(onChange).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({
            file: badFile,
            error: expect.stringContaining("Unsupported format"),
          }),
        ])
      );
    });
  });

  it("validates file size and rejects files exceeding limits", async () => {
    const onChange = jest.fn();
    render(<MediaUploader {...defaultProps} onChange={onChange} mediaType="image" />);

    // 11 MB image (limit is 10 MB)
    const bigFile = createMockFile("big.png", 11 * 1024 * 1024, "image/png");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await userEvent.upload(input, bigFile);

    expect(onChange).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({
          file: bigFile,
          error: expect.stringContaining("File too large"),
        }),
      ])
    );
  });

  it("accepts valid image files without errors", async () => {
    const onChange = jest.fn();
    render(<MediaUploader {...defaultProps} onChange={onChange} mediaType="image" />);

    const validFile = createMockFile("photo.png", 5 * 1024 * 1024, "image/png");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await userEvent.upload(input, validFile);

    expect(onChange).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({
          file: validFile,
          error: undefined,
          preview: "blob:mock-url",
        }),
      ])
    );
  });

  it("validates video file size limit (500MB)", async () => {
    const onChange = jest.fn();
    render(<MediaUploader {...defaultProps} onChange={onChange} mediaType="video" />);

    const bigVideo = createMockFile("big.mp4", 501 * 1024 * 1024, "video/mp4");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await userEvent.upload(input, bigVideo);

    expect(onChange).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({
          error: expect.stringContaining("File too large"),
        }),
      ])
    );
  });

  it("validates audio file size limit (100MB)", async () => {
    const onChange = jest.fn();
    render(<MediaUploader {...defaultProps} onChange={onChange} mediaType="audio" />);

    const bigAudio = createMockFile("big.mp3", 101 * 1024 * 1024, "audio/mpeg");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await userEvent.upload(input, bigAudio);

    expect(onChange).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({
          error: expect.stringContaining("File too large"),
        }),
      ])
    );
  });

  // --- File list display ---

  it("displays selected files with name and size", () => {
    const file = createMockFile("photo.jpg", 2 * 1024 * 1024, "image/jpeg");
    const files: PendingFile[] = [
      { file, preview: "blob:mock", mediaType: "image" },
    ];

    render(<MediaUploader {...defaultProps} files={files} />);

    expect(screen.getByText("photo.jpg")).toBeInTheDocument();
    expect(screen.getByText("2.0 MB")).toBeInTheDocument();
  });

  it("displays validation errors on individual files", () => {
    const file = createMockFile("bad.pdf", 1024, "application/pdf");
    const files: PendingFile[] = [
      { file, preview: null, mediaType: "image", error: "Unsupported format. Allowed: .jpg,.jpeg,.png,.gif" },
    ];

    render(<MediaUploader {...defaultProps} files={files} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/unsupported format/i);
  });

  // --- Remove file ---

  it("removes a file when the remove button is clicked", async () => {
    const onChange = jest.fn();
    const file = createMockFile("photo.jpg", 1024, "image/jpeg");
    const files: PendingFile[] = [
      { file, preview: "blob:mock", mediaType: "image" },
    ];

    render(<MediaUploader {...defaultProps} files={files} onChange={onChange} />);

    const removeBtn = screen.getByRole("button", { name: /remove photo\.jpg/i });
    await userEvent.click(removeBtn);

    expect(onChange).toHaveBeenCalledWith([]);
  });

  // --- Multiple files ---

  it("supports multiple image files up to maxFiles limit", async () => {
    const onChange = jest.fn();
    render(
      <MediaUploader
        {...defaultProps}
        onChange={onChange}
        multiple
        maxFiles={3}
      />
    );

    const files = [
      createMockFile("a.png", 1024, "image/png"),
      createMockFile("b.png", 1024, "image/png"),
      createMockFile("c.png", 1024, "image/png"),
      createMockFile("d.png", 1024, "image/png"),
    ];

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, files);

    // Should be capped at maxFiles=3
    const calledWith = onChange.mock.calls[0][0] as PendingFile[];
    expect(calledWith).toHaveLength(3);
  });

  it("replaces file in single-file mode (video/audio)", async () => {
    const onChange = jest.fn();
    const existingFile = createMockFile("old.mp4", 1024, "video/mp4");
    const existingFiles: PendingFile[] = [
      { file: existingFile, preview: null, mediaType: "video" },
    ];

    render(
      <MediaUploader
        mediaType="video"
        files={existingFiles}
        onChange={onChange}
      />
    );

    const newFile = createMockFile("new.mp4", 2048, "video/mp4");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, newFile);

    // In single mode, should replace with just the new file
    const calledWith = onChange.mock.calls[0][0] as PendingFile[];
    expect(calledWith).toHaveLength(1);
    expect(calledWith[0].file.name).toBe("new.mp4");
  });
});
