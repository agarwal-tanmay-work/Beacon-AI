import type { AttachmentMeta } from "@/types";

// Keep in sync with MAX_UPLOAD_BYTES / MAX_EVIDENCE_FILES_PER_REPORT on the backend. (If a proxy in front of the
// backend rejects large bodies, lower both: NEXT_PUBLIC_MAX_UPLOAD_MB here and MAX_UPLOAD_BYTES there.)
export const MAX_FILE_BYTES = (Number(process.env.NEXT_PUBLIC_MAX_UPLOAD_MB) || 10) * 1024 * 1024;
export const MAX_FILES = 10;

/** What the file picker offers. The backend re-checks the real file type from its bytes. */
export const ACCEPT = "image/*,audio/*,application/pdf,.docx,.txt,.m4a,.heic";

const ALLOWED_EXTENSIONS = new Set([
    "png", "jpg", "jpeg", "webp", "gif", "heic", "heif",
    "mp3", "wav", "m4a", "aac", "ogg", "opus", "flac", "webm", "aiff",
    "pdf", "docx", "txt",
]);

export function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function attachmentKind(file: { type: string; name: string }): AttachmentMeta["type"] {
    if (file.type.startsWith("image/")) return "image";
    if (file.type.startsWith("audio/")) return "audio";
    return "file";
}

/** Returns a user-facing reason if the file should not be attached, otherwise null. */
export function validateFile(file: File, alreadyAttached: number): string | null {
    const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
    if (alreadyAttached >= MAX_FILES) return `You can attach up to ${MAX_FILES} files to one report.`;
    if (file.size === 0) return `"${file.name}" is empty.`;
    if (file.size > MAX_FILE_BYTES) return `"${file.name}" is ${formatSize(file.size)} - the limit is ${formatSize(MAX_FILE_BYTES)} per file.`;
    const looksAllowed = file.type.startsWith("image/") || file.type.startsWith("audio/") || file.type === "application/pdf" || ALLOWED_EXTENSIONS.has(extension);
    return looksAllowed ? null : `"${file.name}" is not a supported type. Please use photos, audio recordings, PDFs, Word documents or text files.`;
}

export function newId(): string {
    return typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
