"use client";

// Progress for the student on this device: streak, totals, mistakes that keep coming back, chapters to revise, recent checks.

import Link from "next/link";
import { useProgress, useStudent } from "@/lib/student";
import { formatMarks } from "@/components/math";
import { Notice } from "@/components/ui";

export function ProgressView() {
  const student = useStudent();
  const progress = useProgress(student);

  if (!student || (progress && progress.checks_done === 0)) {
    return (
      <Notice
        tone="info"
        title="No sums checked yet"
        action={
          <Link href="/check" className="rounded-full bg-red-pen px-4 py-1.5 text-sm font-semibold text-white">
            Check your first sum
          </Link>
        }
      >
        Your streak, strong chapters and weak chapters show up here after your first check.
      </Notice>
    );
  }
  if (!progress) return <div className="h-48 animate-pulse rounded-3xl bg-paper-deep" aria-label="Loading progress" />;

  // One slip is a slip; the same kind twice is a pattern worth showing.
  const recurring = progress.mistakes.filter((item) => item.times >= 2);
  const stats = [
    { value: `${progress.streak_days}`, label: "day streak" },
    { value: progress.checks_done, label: "sums checked" },
    { value: progress.full_marks, label: "full marks" },
    { value: progress.mistakes_fixed, label: "mistakes fixed with the tutor" },
  ];

  return (
    <div className="space-y-8">
      <section aria-label="Your numbers" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.label} className="rounded-2xl border border-rule bg-card p-4">
            <p className="text-2xl font-extrabold">{stat.value}</p>
            <p className="text-xs text-muted">{stat.label}</p>
          </div>
        ))}
      </section>
      {!progress.checked_today ? (
        <Notice
          tone="info"
          title={progress.streak_days > 0 ? "Keep your streak alive" : "Start a streak today"}
          action={
            <Link href="/check" className="rounded-full bg-red-pen px-4 py-1.5 text-sm font-semibold text-white">
              Check today&apos;s sum
            </Link>
          }
        >
          One checked sum a day is enough.
        </Notice>
      ) : null}

      {recurring.length > 0 ? (
        <section className="space-y-3">
          <h2 className="text-lg font-bold">Mistakes that keep coming back</h2>
          <ul className="space-y-2">
            {recurring.map((item) => (
              <li
                key={item.mistake}
                className="flex items-start justify-between gap-3 rounded-2xl border border-rule bg-card p-4 text-sm"
              >
                <div className="min-w-0">
                  <p className="font-semibold first-letter:uppercase">{item.mistake}</p>
                  <p className="text-xs text-muted">{item.chapters.join(" · ")}</p>
                </div>
                <span className="shrink-0 font-hand text-2xl font-bold text-red-pen">{item.times}×</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="space-y-3">
        <h2 className="text-lg font-bold">Chapters (weakest first)</h2>
        <ul className="space-y-3">
          {progress.chapters.map((chapter) => {
            const share = chapter.full_marks / chapter.attempts;
            return (
              <li key={chapter.chapter} className="rounded-2xl border border-rule bg-card p-4">
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span className="font-semibold">
                    {chapter.chapter}
                    {chapter.needs_revision ? (
                      <span className="ml-2 rounded-full bg-amber-soft px-2 py-0.5 text-xs font-semibold text-amber">
                        revise
                      </span>
                    ) : null}
                  </span>
                  <span className="text-muted">
                    {chapter.full_marks}/{chapter.attempts} full marks
                  </span>
                </div>
                <div
                  className="mt-2 h-2.5 overflow-hidden rounded-full bg-paper-deep"
                  role="img"
                  aria-label={`${Math.round(share * 100)}% full marks`}
                >
                  <div
                    className={`h-full rounded-full ${share >= 0.7 ? "bg-green-tick" : share >= 0.4 ? "bg-amber" : "bg-red-pen"}`}
                    style={{ width: `${Math.max(4, Math.round(share * 100))}%` }}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">Recent sums</h2>
        <ul className="divide-y divide-rule overflow-hidden rounded-2xl border border-rule bg-card">
          {progress.recent.map((item) => (
            <li key={item.check_id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
              <div className="min-w-0">
                <p className="truncate font-semibold">{item.question_text.replace(/\$/g, "")}</p>
                <p className="text-xs text-muted">
                  {item.chapter} · {new Date(item.created_at).toLocaleDateString("en-IN")}
                </p>
              </div>
              <span
                className={`shrink-0 font-hand text-2xl font-bold ${item.score === item.max_score ? "text-green-tick" : "text-red-pen"}`}
              >
                {formatMarks(item.score)}/{item.max_score}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
