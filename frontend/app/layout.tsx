import type { Metadata } from "next";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import "./globals.css";

export const metadata: Metadata = {
  title: "Second Voice — Your Voice. Your Meaning. Your Choice.",
  description: "Assistive communication for speech intelligibility difficulties. AI suggests; you decide; only confirmed text is spoken.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Manrope:wght@600;700&display=swap"
          rel="stylesheet"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200"
          rel="stylesheet"
        />
      </head>
      <body className="bg-surface text-on-surface font-body-md text-body-md antialiased min-h-screen">
        <Header />
        <main className="fade-in w-full pt-20 bg-surface min-h-[calc(100vh-200px)]">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
