// Solve one question: show your working, get the red pen, talk to the tutor.

import type { Metadata } from "next";
import { Suspense } from "react";
import { SolveFlow } from "@/components/solve-flow";

export const metadata: Metadata = { title: "Solve · Samjho" };

async function Flow({ params }: { params: Promise<{ questionId: string }> }) {
  const { questionId } = await params;
  return <SolveFlow questionId={questionId} />;
}

export default function SolvePage({ params }: PageProps<"/solve/[questionId]">) {
  return (
    <Suspense fallback={<div className="h-40 animate-pulse rounded-3xl bg-paper-deep" />}>
      <Flow params={params} />
    </Suspense>
  );
}
