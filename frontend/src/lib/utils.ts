import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Parses API timestamps. The backend sends UTC ("...Z"); strings without a zone are treated as UTC too. */
function parseTimestamp(value: string | Date | number): Date {
  if (typeof value !== "string") return new Date(value);
  let text = value.trim();
  if (text.includes(" ") && !text.includes("T")) text = text.replace(" ", "T");
  const hasZone = /Z|[+-]\d{2}:?\d{2}$/.test(text) || /GMT|UTC/i.test(text);
  return new Date(hasZone ? text : `${text}Z`);
}

/** Formats a timestamp in Indian Standard Time. Pass `{ hour: undefined, minute: undefined }` for a date only. */
export function formatToIST(value: string | Date | number | null | undefined, options: Intl.DateTimeFormatOptions = {}): string {
  if (!value) return "";
  const date = parseTimestamp(value);
  if (Number.isNaN(date.getTime())) return String(value);

  const merged: Intl.DateTimeFormatOptions = {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
    ...options,
  };
  const cleaned = Object.fromEntries(Object.entries(merged).filter(([, v]) => v !== undefined)) as Intl.DateTimeFormatOptions;
  return new Intl.DateTimeFormat("en-IN", cleaned).format(date);
}
