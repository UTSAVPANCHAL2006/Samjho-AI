"use client";

// Edit the lines of working: type them yourself, or fix what we read from your photo.
// Our reading mistakes must never cost the student marks, so they always get the last word.

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { TYPING_EXAMPLES, toPreviewLatex } from "@/lib/plain-maths";
import { MathText } from "@/components/math";

interface Line {
  key: number;
  text: string;
  needsCheck: boolean;
}

export function LinesEditor({
  lines,
  photoUrl,
  isBusy,
  title,
  intro,
  onSubmit,
}: {
  lines: { latex: string; needs_check: boolean }[];
  photoUrl: string | null;
  isBusy: boolean;
  title: string;
  intro: string;
  onSubmit: (lines: string[]) => void;
}) {
  const [rows, setRows] = useState<Line[]>(() =>
    lines.length
      ? lines.map((line, index) => ({ key: index, text: line.latex, needsCheck: line.needs_check }))
      : [{ key: 0, text: "", needsCheck: false }],
  );
  const listRef = useRef<HTMLOListElement>(null);
  const focusAfterAdd = useRef<number | null>(null);
  const unsureCount = rows.filter((row) => row.needsCheck).length;

  const focusRow = (index: number) => listRef.current?.querySelectorAll<HTMLInputElement>("input")[index]?.focus();

  useEffect(() => {
    if (focusAfterAdd.current !== null) focusRow(focusAfterAdd.current);
    focusAfterAdd.current = null;
  }, [rows.length]);

  function addRow() {
    setRows((current) => [
      ...current,
      { key: Math.max(...current.map((row) => row.key), 0) + 1, text: "", needsCheck: false },
    ]);
  }

  // Enter = next step, like the next line in a notebook.
  function onKeyDown(event: KeyboardEvent<HTMLInputElement>, index: number) {
    if (event.key !== "Enter") return;
    event.preventDefault();
    if (index < rows.length - 1) return focusRow(index + 1);
    if (rows[index].text.trim()) {
      focusAfterAdd.current = index + 1;
      addRow();
    }
  }

  return (
    <div className={`fade-up grid gap-6 ${photoUrl ? "lg:grid-cols-[1fr_1.1fr]" : ""}`}>
      {photoUrl ? (
        // eslint-disable-next-line @next/next/no-img-element -- the photo comes from our API
        <img
          src={photoUrl}
          alt="Your working"
          className="max-h-[32rem] w-full rounded-2xl border border-rule object-contain"
        />
      ) : null}
      <div className="space-y-4">
        <div>
          <h2 className="text-xl font-bold">{title}</h2>
          <p className="text-sm text-muted">{intro}</p>
          {unsureCount ? (
            <p className="mt-2 text-sm font-semibold text-amber">
              {unsureCount === 1 ? "1 line needs" : `${unsureCount} lines need`} your check — we were not sure we read
              it right.
            </p>
          ) : null}
        </div>
        <ol ref={listRef} className="space-y-3">
          {rows.map((row, index) => (
            <li
              key={row.key}
              className={`rounded-2xl border bg-card p-3 ${row.needsCheck ? "border-amber ring-2 ring-amber/30" : "border-rule"}`}
            >
              <div className="flex items-center justify-between text-xs text-muted">
                <span>Line {index + 1}</span>
                <button
                  type="button"
                  onClick={() => setRows((current) => current.filter((item) => item.key !== row.key))}
                  aria-label={`Remove line ${index + 1}`}
                  className="rounded px-2 py-0.5 hover:text-red-pen"
                >
                  Remove
                </button>
              </div>
              <div className="min-h-8 py-1 text-lg">
                {row.text.trim() ? (
                  <MathText latex={toPreviewLatex(row.text)} />
                ) : (
                  <span className="text-muted">Empty line</span>
                )}
              </div>
              <input
                value={row.text}
                onChange={(event) =>
                  setRows((current) =>
                    current.map((item) =>
                      item.key === row.key ? { ...item, text: event.target.value, needsCheck: false } : item,
                    ),
                  )
                }
                onKeyDown={(event) => onKeyDown(event, index)}
                aria-label={`Line ${index + 1}`}
                placeholder={index === 0 ? "your first step" : "next step…"}
                className="w-full rounded-xl border border-rule bg-paper px-3 py-2 font-mono text-sm focus:border-ink-soft focus:outline-none"
              />
            </li>
          ))}
        </ol>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={addRow}
            className="rounded-full px-4 py-2 text-sm font-semibold text-ink-soft ring-1 ring-rule hover:ring-ink-soft"
          >
            + Add line
          </button>
          <button
            type="button"
            disabled={isBusy || !rows.some((row) => row.text.trim())}
            onClick={() => onSubmit(rows.map((row) => row.text.trim()).filter(Boolean))}
            className="rounded-full bg-red-pen px-6 py-2 text-sm font-semibold text-white hover:brightness-110 disabled:opacity-50"
          >
            {isBusy ? "Checking…" : "Check my work"}
          </button>
        </div>
        <details open={!photoUrl} className="rounded-2xl bg-paper-deep/60 p-3 text-sm">
          <summary className="cursor-pointer font-semibold text-ink-soft">
            ✍️ Type maths like you say it — no special keyboard
          </summary>
          <ul className="mt-2 grid gap-1.5 sm:grid-cols-2">
            {TYPING_EXAMPLES.map((example) => (
              <li
                key={example.typed}
                className="flex items-center justify-between gap-2 rounded-lg bg-card px-3 py-1.5"
              >
                <code className="text-xs text-ink-soft">{example.typed}</code>
                <span>
                  → <MathText latex={example.meaning} />
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-muted">
            Press Enter for the next step. The preview above each box is exactly what we will check.
          </p>
        </details>
      </div>
    </div>
  );
}
