"use client";

// Practise: pick your class, then any question from the bank, grouped by chapter.

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Question } from "@/lib/api";
import { useStudent } from "@/lib/student";
import { QuestionText, formatDifficulty } from "@/components/math";
import { Notice } from "@/components/ui";

export function PracticeList() {
  const student = useStudent();
  const [chosenClass, setChosenClass] = useState<number | null>(null);
  const classLevel = chosenClass ?? student?.class_level ?? 10;
  const [loaded, setLoaded] = useState<{ classLevel: number; questions: Question[] } | "failed" | null>(null);

  useEffect(() => {
    let isCurrent = true;
    api
      .listQuestions(classLevel)
      .then((questions) => isCurrent && setLoaded({ classLevel, questions }))
      .catch(() => isCurrent && setLoaded("failed"));
    return () => {
      isCurrent = false;
    };
  }, [classLevel]);

  const isFailed = loaded === "failed";
  const questions = loaded && loaded !== "failed" && loaded.classLevel === classLevel ? loaded.questions : null;
  const chapters = new Map<string, Question[]>();
  for (const question of questions ?? [])
    chapters.set(question.chapter, [...(chapters.get(question.chapter) ?? []), question]);

  return (
    <div className="space-y-6">
      <div role="tablist" aria-label="Choose your class" className="flex flex-wrap gap-2">
        {[6, 7, 8, 9, 10].map((level) => (
          <button
            key={level}
            role="tab"
            aria-selected={level === classLevel}
            onClick={() => setChosenClass(level)}
            className={`rounded-full px-5 py-2 text-sm font-semibold transition ${level === classLevel ? "bg-ink text-white" : "bg-card text-ink-soft ring-1 ring-rule hover:ring-ink-soft"}`}
          >
            Class {level}
          </button>
        ))}
      </div>
      {isFailed ? (
        <Notice tone="error" title="Questions did not load">
          We can&apos;t reach Samjho right now. Check your internet and refresh the page.
        </Notice>
      ) : null}
      {!questions && !isFailed ? (
        <div className="h-40 animate-pulse rounded-2xl bg-paper-deep" aria-label="Loading questions" />
      ) : null}
      {[...chapters.entries()].map(([chapter, items]) => (
        <section key={chapter} className="fade-up space-y-3">
          <h2 className="text-lg font-bold">{chapter}</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {items.map((question) => (
              <Link
                key={question.id}
                href={`/solve/${question.id}`}
                className="group flex flex-col justify-between gap-3 rounded-2xl border border-rule bg-card p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-ink-soft hover:shadow-md"
              >
                <QuestionText text={question.text} expressions={question.expressions} size="small" />
                <span className="flex items-center justify-between text-xs text-muted">
                  {formatDifficulty(question.difficulty)} · {question.marks} marks
                  <span className="font-semibold text-red-pen transition group-hover:translate-x-0.5">Solve →</span>
                </span>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
