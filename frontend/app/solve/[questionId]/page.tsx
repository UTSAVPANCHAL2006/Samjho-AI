// Solve one question: show your working, get the red pen, talk to the tutor.

import type { Metadata } from "next";
import { SolveFromUrl } from "@/components/solve-flow";

export const metadata: Metadata = { title: "Solve · Samjho" };

export default function SolvePage() {
  return <SolveFromUrl />;
}
