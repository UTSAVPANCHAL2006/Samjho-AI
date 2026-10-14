// Main entry, step 1 of 3: a photo of ANY Class 6–10 maths question.
// Step 2 (your working) and step 3 (red-pen check) happen on /solve/[questionId].

import type { Metadata } from "next";
import Link from "next/link";
import { QuestionAsker } from "@/components/question-asker";
import { StudentSetup } from "@/components/student";
import { JourneySteps } from "@/components/ui";

export const metadata: Metadata = { title: "Check a sum · Samjho" };

export default function CheckPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-7">
      <StudentSetup />
      <JourneySteps activeStep={1} />
      <header className="space-y-2.5 px-1">
        <p className="eyebrow">Step 1 of 3 · Any Class 6–10 maths sum</p>
        <h1 className="text-4xl font-extrabold sm:text-5xl">Which question are you solving?</h1>
        <p className="max-w-2xl leading-relaxed text-muted">
          Any chapter, any book — NCERT, RD Sharma, RS Aggarwal, a worksheet or a test paper. Take a photo of the
          question; next, a photo of your working.
        </p>
      </header>
      <QuestionAsker />
      <p className="text-center text-sm text-muted">
        Just want some practice?{" "}
        <Link href="/practice" className="font-semibold text-red-pen underline-offset-2 hover:underline">
          Browse practice questions by class
        </Link>
      </p>
    </div>
  );
}
