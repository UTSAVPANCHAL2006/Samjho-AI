"use client";

// Lab body: pick a class, see one question per chapter, open its concept visual.

import { useEffect, useState } from "react";
import { api, type Question } from "@/lib/api";
import { QuestionText } from "@/components/math";
import { VisualCard } from "@/components/visual-card";

const CLASS_LEVELS = [6, 7, 8, 9, 10];

function onePerChapter(questions: Question[]): Question[] {
  const seen = new Set<string>();
  return questions.filter((question) => !seen.has(question.chapter) && seen.add(question.chapter));
}

export function VisualLab() {
  const [classLevel, setClassLevel] = useState(8);
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    let isCurrent = true;
    void api
      .listQuestions(classLevel)
      .then((list) => isCurrent && setQuestions(onePerChapter(list)))
      .catch(() => isCurrent && setQuestions([]));
    return () => {
      isCurrent = false;
    };
  }, [classLevel]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-2">
        {CLASS_LEVELS.map((level) => (
          <button
            key={level}
            onClick={() => {
              setQuestions(null);
              setOpenId(null);
              setClassLevel(level);
            }}
            className={`rounded-full px-5 py-2 text-sm font-semibold ${level === classLevel ? "bg-ink text-white" : "bg-card ring-1 ring-rule"}`}
          >
            Class {level}
          </button>
        ))}
      </div>
      {questions === null ? <div className="h-32 animate-pulse rounded-2xl bg-paper-deep" /> : null}
      <ul className="space-y-3">
        {(questions ?? []).map((question) => (
          <li key={question.id} className="space-y-3 rounded-2xl border border-rule bg-card p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-wide text-red-pen">{question.chapter}</p>
                <QuestionText text={question.text} expressions={question.expressions} size="small" />
              </div>
              <button
                onClick={() => setOpenId(openId === question.id ? null : question.id)}
                className="shrink-0 rounded-full px-3 py-1.5 text-sm font-semibold ring-1 ring-rule hover:ring-ink-soft"
              >
                {openId === question.id ? "Close" : "Visual"}
              </button>
            </div>
            {openId === question.id ? <VisualCard key={question.id} questionId={question.id} autoOpen /> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
