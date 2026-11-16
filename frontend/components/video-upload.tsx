"use client";

import { useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { CheckCircle2, FileVideo2, LoaderCircle, UploadCloud, X } from "lucide-react";
import { ApiError, uploadVideo, type Video } from "@/lib/api";
import {
  formatFileSize,
  MAX_UPLOAD_SIZE_LABEL,
  validateVideoUpload,
} from "@/lib/videos";

interface VideoUploadProps {
  accessToken: string;
  onUploaded: (video: Video) => void | Promise<void>;
}

export function VideoUpload({
  accessToken,
  onUploaded,
}: VideoUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  function chooseFile(file: File | undefined) {
    if (!file) {
      return;
    }
    setSuccess("");
    const validationError = validateVideoUpload(file);
    if (validationError) {
      setSelectedFile(null);
      setError(validationError);
      return;
    }
    setError("");
    setProgress(null);
    setSelectedFile(file);
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    chooseFile(event.target.files?.[0]);
    event.target.value = "";
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    chooseFile(event.dataTransfer.files[0]);
  }

  async function handleUpload() {
    if (!selectedFile || isUploading) {
      return;
    }
    let uploadedVideo: Video | null = null;
    setError("");
    setSuccess("");
    setProgress(0);
    setIsUploading(true);
    try {
      uploadedVideo = await uploadVideo(accessToken, selectedFile, setProgress);
      setSuccess(`${uploadedVideo.original_filename} was uploaded successfully.`);
      setSelectedFile(null);
    } catch (reason) {
      setError(
        reason instanceof ApiError
          ? reason.message
          : "The upload could not be completed. Please try again.",
      );
    } finally {
      setIsUploading(false);
    }
    // Refreshing the listing is separate. A refresh failure must not make a
    // successful upload look as though the file was rejected.
    if (!uploadedVideo) {
      return;
    }
    try {
      await onUploaded(uploadedVideo);
    } catch {
      setError("The video was uploaded, but the library could not refresh. Use Refresh to reload it.");
    }
  }

  return (
    <section
      aria-labelledby="video-upload-title"
      className="rounded-xl border border-line bg-white p-5 sm:p-6"
    >
      <div className="mb-5 flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-blue-200 bg-blue-50 text-blue-700">
          <UploadCloud aria-hidden="true" className="h-5 w-5" />
        </span>
        <div>
          <h2 id="video-upload-title" className="text-sm font-semibold text-slate-900">
            Upload road footage
          </h2>
          <p className="mt-1 text-xs leading-5 text-slate-600">
            MP4, MOV, AVI, or MKV · up to {MAX_UPLOAD_SIZE_LABEL}
          </p>
        </div>
      </div>

      <div
        className={`rounded-xl border border-dashed px-4 py-6 text-center transition ${
          isDragging
            ? "border-blue-300 bg-blue-50"
            : "border-slate-700 bg-slate-50 hover:border-slate-500"
        }`}
        onDragEnter={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={(event) => {
          event.preventDefault();
          setIsDragging(false);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDrop={handleDrop}
      >
        <input
          accept=".mp4,.mov,.avi,.mkv,video/mp4,video/quicktime,video/x-msvideo,video/x-matroska"
          aria-label="Choose video file"
          className="sr-only"
          disabled={isUploading}
          onChange={handleFileChange}
          ref={inputRef}
          type="file"
        />
        {selectedFile ? (
          <div className="flex flex-col items-center">
            <FileVideo2 aria-hidden="true" className="h-7 w-7 text-blue-700" />
            <p className="mt-3 max-w-full truncate text-sm font-medium text-slate-700">
              {selectedFile.name}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {formatFileSize(selectedFile.size)}
            </p>
            {!isUploading && (
              <button
                className="mt-2 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700"
                onClick={() => setSelectedFile(null)}
                type="button"
              >
                <X aria-hidden="true" className="h-3.5 w-3.5" />
                Remove selection
              </button>
            )}
          </div>
        ) : (
          <>
            <UploadCloud
              aria-hidden="true"
              className="mx-auto h-7 w-7 text-slate-500"
            />
            <p className="mt-3 text-sm text-slate-600">
              Drop a video here or{" "}
              <button
                className="font-medium text-blue-700 underline decoration-sky-200/30 underline-offset-4 hover:text-slate-900"
                disabled={isUploading}
                onClick={() => inputRef.current?.click()}
                type="button"
              >
                browse files
              </button>
            </p>
            <p className="mt-1 text-xs text-slate-600">
              Files are checked again by the protected API before storage.
            </p>
          </>
        )}
      </div>

      {isUploading && (
        <div className="mt-4" aria-live="polite">
          <div className="flex justify-between text-xs text-slate-600">
            <span>Uploading video</span>
            <span>{progress === null ? "Sending…" : `${progress}%`}</span>
          </div>
          <div
            aria-label="Upload progress"
            aria-valuemax={100}
            aria-valuemin={0}
            aria-valuenow={progress ?? 0}
            className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-800"
            role="progressbar"
          >
            <div
              className="h-full rounded-full bg-sky-400 transition-[width]"
              style={{ width: `${progress ?? 4}%` }}
            />
          </div>
        </div>
      )}

      {error && (
        <p className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700" role="alert">
          {error}
        </p>
      )}
      {success && (
        <p className="mt-4 inline-flex items-center gap-2 text-sm text-emerald-800" role="status">
          <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
          {success}
        </p>
      )}

      <button
        className="primary-button mt-4 sm:w-auto"
        disabled={!selectedFile || isUploading}
        onClick={() => void handleUpload()}
        type="button"
      >
        {isUploading ? (
          <>
            <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
            Uploading
          </>
        ) : (
          <>
            <UploadCloud aria-hidden="true" className="h-4 w-4" />
            Upload video
          </>
        )}
      </button>
    </section>
  );
}
