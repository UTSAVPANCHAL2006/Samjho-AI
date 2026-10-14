// Progress for the student on this device.

import type { Metadata } from "next";
import { ProgressView } from "@/components/progress-view";

export const metadata: Metadata = { title: "My progress · Samjho" };

export default function ProgressPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-extrabold tracking-tight">My progress</h1>
      <ProgressView />
    </div>
  );
}
