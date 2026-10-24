import type { Metadata } from "next";

// Case lookup pages have no business in search results.
export const metadata: Metadata = {
  title: "Track Status",
  robots: { index: false, follow: false },
};

export default function TrackLayout({ children }: { children: React.ReactNode }) {
  return children;
}
