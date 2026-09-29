import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Gita Guide",
  description: "Grounded reflections from the Bhagavad Gita for life's difficult moments.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
