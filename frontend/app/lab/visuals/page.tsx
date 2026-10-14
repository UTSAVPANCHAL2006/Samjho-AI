// Lab: try the AI concept visuals on one question from every chapter of a class (for checking quality).

import type { Metadata } from "next";
import { VisualLab } from "@/components/visual-lab";

export const metadata: Metadata = { title: "Visual lab · Samjho" };

export default function VisualLabPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <p className="text-sm font-bold uppercase tracking-wide text-red-pen">Lab</p>
        <h1 className="text-3xl font-extrabold tracking-tight">Concept visuals</h1>
        <p className="text-muted">One question from every chapter. Open any one to see the AI-designed, maths-checked visual.</p>
      </header>
      <VisualLab />
    </div>
  );
}
