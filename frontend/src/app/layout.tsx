import type { Metadata } from "next";
import { Figtree, Instrument_Serif, JetBrains_Mono } from "next/font/google";

import { AuthProvider } from "@/components/auth/AuthProvider";
import { Footer } from "@/components/layout/Footer";
import { Navbar } from "@/components/layout/Navbar";

import "./globals.css";

const figtree = Figtree({
  variable: "--font-figtree",
  subsets: ["latin"],
});

const instrumentSerif = Instrument_Serif({
  variable: "--font-instrument-serif",
  subsets: ["latin"],
  weight: "400",
  style: "italic",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "Zenvy — Crop disease & yield insights",
    template: "%s · Zenvy",
  },
  description:
    "Detect crop diseases from a leaf photo and estimate yield before harvest, with the reasoning shown.",
  applicationName: "Zenvy",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${figtree.variable} ${instrumentSerif.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-dvh flex-col bg-page text-ink">
        <AuthProvider>
          <a
            href="#content"
            className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:shadow"
          >
            Skip to content
          </a>
          <Navbar />
          <main id="content" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:py-12">
            {children}
          </main>
          <Footer />
        </AuthProvider>
      </body>
    </html>
  );
}
