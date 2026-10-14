// Root layout: fonts, header and footer shared by every page.

import type { Metadata } from "next";
import { Bricolage_Grotesque, Caveat, Kalam, Plus_Jakarta_Sans } from "next/font/google";
import { Header } from "@/components/header";
import "./globals.css";

const bodyFont = Plus_Jakarta_Sans({ variable: "--font-body", subsets: ["latin"] });
const displayFont = Bricolage_Grotesque({ variable: "--font-display", subsets: ["latin"] });
const chalkFont = Kalam({ variable: "--font-chalk", subsets: ["latin", "devanagari"], weight: ["400", "700"] });
const handFont = Caveat({ variable: "--font-hand", subsets: ["latin"], weight: ["500", "700"] });

export const metadata: Metadata = {
  title: "Samjho — spot the mistake, understand it",
  description:
    "Check any CBSE Class 6–10 maths sum line by line, then talk through your own mistake with a voice tutor in Hinglish or English.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${bodyFont.variable} ${displayFont.variable} ${chalkFont.variable} ${handFont.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <Header />
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 pb-20 pt-8 sm:px-6">{children}</main>
        <footer className="border-t border-rule/80 px-4 py-8 text-center text-sm text-muted">
          <span className="font-display font-bold text-ink">Samjho</span> · CBSE Class 6–10 Maths · Every mark is checked
          by maths, never guessed by AI.
        </footer>
      </body>
    </html>
  );
}
