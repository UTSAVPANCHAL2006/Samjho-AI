// Practise: extra questions from the bank, by class and chapter. The main way in is /check (any sum).

import type { Metadata } from "next";
import Link from "next/link";
import { PracticeList } from "@/components/practice-list";

export const metadata: Metadata = { title: "Practise · Samjho" };

export default function PracticePage() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-extrabold tracking-tight">Practise</h1>
        <p className="text-muted">
          Pick a question, solve it on paper, then show your working. Have your own sum?{" "}
          <Link href="/check" className="font-semibold text-red-pen underline-offset-2 hover:underline">
            Check any sum
          </Link>
        </p>
      </header>
      <PracticeList />
    </div>
  );
}
