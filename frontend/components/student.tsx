"use client";

// The student: a header chip (name, streak, switch), a first-visit "who are you?" card,
// and the home-page "welcome back" strip that brings them back for one sum a day.

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { ArrowRightIcon, FlameIcon, PenIcon } from "@/components/icons";
import { signIn, switchStudent, useProgress, useStudent } from "@/lib/student";

export function StudentChip() {
  const student = useStudent();
  const progress = useProgress(student);
  if (!student || student.name === "Student") return null;
  return (
    <div className="hidden items-center gap-2 rounded-full bg-card py-1 pl-1 pr-3 text-sm shadow-sm ring-1 ring-rule sm:flex">
      <span className="grid h-7 w-7 place-items-center rounded-full bg-ink text-xs font-bold text-white">
        {student.name.charAt(0).toUpperCase()}
      </span>
      <span className="font-semibold">{student.name}</span>
      {progress && progress.streak_days > 0 ? (
        <span className="flex items-center gap-0.5 font-semibold text-amber" title={`${progress.streak_days}-day streak`}>
          <FlameIcon size={15} /> {progress.streak_days}
        </span>
      ) : null}
      <button onClick={switchStudent} className="text-xs text-muted hover:text-ink" title="Switch student">
        Switch
      </button>
    </div>
  );
}

export function StudentSetup() {
  const student = useStudent();
  const [name, setName] = useState("");
  const [classLevel, setClassLevel] = useState(10);
  const [isSkipped, setIsSkipped] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if ((student && student.name !== "Student") || isSkipped) return null;

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) return;
    try {
      await signIn(name.trim(), classLevel);
    } catch {
      setError("Could not save. You can still check sums as a guest.");
    }
  }

  return (
    <form
      onSubmit={save}
      aria-label="Tell us who you are"
      className="fade-up surface flex flex-col gap-3 p-4 sm:flex-row sm:items-end sm:p-5"
    >
      <label className="flex-1 space-y-1 text-sm">
        <span className="font-semibold">Your name</span>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={40}
          aria-label="Your name"
          placeholder="So we can track YOUR progress"
          className="w-full rounded-2xl border border-rule bg-paper px-4 py-2.5 focus:border-ink-soft focus:outline-none"
        />
      </label>
      <label className="space-y-1 text-sm">
        <span className="font-semibold">Class</span>
        <select
          value={classLevel}
          onChange={(event) => setClassLevel(Number(event.target.value))}
          className="block rounded-2xl border border-rule bg-paper px-3 py-2.5"
        >
          {[6, 7, 8, 9, 10].map((level) => (
            <option key={level} value={level}>
              Class {level}
            </option>
          ))}
        </select>
      </label>
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={!name.trim()}
          className="rounded-2xl bg-ink px-5 py-2.5 text-sm font-semibold text-white transition disabled:opacity-35"
        >
          Save
        </button>
        <button
          type="button"
          onClick={() => setIsSkipped(true)}
          className="rounded-xl px-3 py-2 text-sm text-muted hover:text-ink"
        >
          Skip
        </button>
      </div>
      {error ? <p className="text-sm text-red-pen sm:basis-full">{error}</p> : null}
    </form>
  );
}

const count = (value: number, noun: string) => `${value} ${noun}${value === 1 ? "" : "s"}`;

export function WelcomeBack() {
  const student = useStudent();
  const progress = useProgress(student);
  if (!progress || progress.checks_done === 0) return null;
  const firstName = progress.name === "Student" ? "" : ` ${progress.name.split(" ")[0]}`;
  const goal = progress.checked_today
    ? "Today's sum is done. One more keeps the mind sharp."
    : progress.streak_days > 0
      ? `Check one sum today to keep your ${progress.streak_days}-day streak.`
      : "Check one sum today to start a streak.";
  return (
    <section className="fade-up surface flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
      <div className="flex items-center gap-4">
        <span
          className={`grid h-12 w-12 shrink-0 place-items-center rounded-2xl ${progress.streak_days > 0 ? "bg-amber-soft text-amber" : "bg-paper text-ink-soft"}`}
          aria-hidden
        >
          {progress.streak_days > 0 ? <FlameIcon size={26} /> : <PenIcon size={24} />}
        </span>
        <div>
          <p className="font-display text-lg font-bold tracking-tight">
            Welcome back{firstName}!{" "}
            {progress.streak_days > 0 ? <span className="text-amber">{progress.streak_days}-day streak</span> : null}
          </p>
          <p className="text-sm text-ink-soft">{goal}</p>
          <p className="mt-0.5 text-xs text-muted">
            {count(progress.checks_done, "sum")} checked · {count(progress.mistakes_fixed, "mistake")} fixed
            {progress.chapters[0] ? ` · next focus: ${progress.chapters[0].chapter}` : ""}
          </p>
        </div>
      </div>
      <Link href="/check" className="btn-primary shrink-0 px-5 py-2.5 text-sm">
        {progress.checked_today ? "Check another sum" : "Do today's sum"} <ArrowRightIcon size={16} />
      </Link>
    </section>
  );
}
