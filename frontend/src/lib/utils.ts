import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatToIST(date: string | Date | number, options: Intl.DateTimeFormatOptions = {}) {
  if (!date) return "";

  try {
    let d: Date;
    if (typeof date === 'string') {
      let dateStr = date.trim();
      // Ensure ISO format T
      if (dateStr.includes(' ') && !dateStr.includes('T')) {
        dateStr = dateStr.replace(' ', 'T');
      }

      // Check for various timezone indicators including Z, offsets (+05:30), or GMT/UTC suffixes
      const hasTimezone = /Z|([+-]\d{2}:?\d{2})$/.test(dateStr) || /GMT|UTC/i.test(dateStr);

      // Assume UTC if no timezone info is present
      if (!hasTimezone) {
        dateStr += 'Z';
      }
      d = new Date(dateStr);
    } else {
      d = new Date(date);
    }

    if (isNaN(d.getTime())) {
      console.warn("formatToIST received invalid date:", date);
      return String(date);
    }

    const finalOptions: Intl.DateTimeFormatOptions = {
      timeZone: 'Asia/Kolkata',
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
      ...options
    };

    // Filter undefined values
    const cleanOptions = Object.fromEntries(
      Object.entries(finalOptions).filter(([_, v]) => v !== undefined)
    );

    return new Intl.DateTimeFormat('en-IN', cleanOptions).format(d);
  } catch (e) {
    console.error("formatToIST error:", e);
    return String(date);
  }
}
