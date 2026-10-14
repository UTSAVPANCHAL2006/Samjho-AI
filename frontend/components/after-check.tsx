"use client";

// The next practice question, shown right after a check (always from the same chapter).

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Question } from "@/lib/api";
import { readStudent } from "@/lib/student";
import { QuestionText, formatDifficulty } from "@/components/math";

export function PracticeCard({ checkId, title }: { checkId: string; title: string }) {
  const [state, setState] = useState<{ question: Question | null; reason: string } | "loading" | "failed">("loading");

  useEffect(() => {
    let isCurrent = true;
    api
      .nextPractice(checkId, readStudent()?.id ?? null)
      .then((result) => isCurrent && setState(result))
      .catch(() => isCurrent && setState("failed"));
    return () => {
      isCurrent = false;
    };
  }, [checkId]);

  if (state === "loading")
    return <div className="h-32 animate-pulse rounded-2xl bg-paper-deep" aria-label="Loading practice question" />;
  if (state === "failed" || !state.question) {
    return (
      <Link
        href="/check"
        className="block rounded-2xl border border-rule bg-card p-4 text-sm font-semibold text-red-pen"
      >
        Check another sum →
      </Link>
    );
  }
  return (
    <section
      aria-label="Practice question"
      className="fade-up space-y-3 rounded-2xl border-2 border-ink bg-card p-5 shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-bold uppercase tracking-wide text-red-pen">{title}</p>
        <span className="text-xs text-muted">
          {state.reason} · {formatDifficulty(state.question.difficulty)}
        </span>
      </div>
      <QuestionText text={state.question.text} expressions={state.question.expressions} />
      <Link
        href={`/solve/${state.question.id}`}
        className="inline-flex rounded-full bg-ink px-5 py-2.5 text-sm font-semibold text-white hover:bg-ink-soft"
      >
        Solve this one →
      </Link>
    </section>
  );
}
