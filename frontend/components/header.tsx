// Top bar: logo, the three places a student goes (check a sum, practise, progress) and who is studying.

import Link from "next/link";
import { StudentChip } from "@/components/student";

export function Header() {
  return (
    <header className="sticky top-0 z-20 border-b border-rule/70 bg-paper/75 backdrop-blur-xl backdrop-saturate-150">
      <nav className="mx-auto flex max-w-5xl items-center justify-between gap-2 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2" aria-label="Samjho home">
          <span className="grid h-9 w-9 -rotate-6 place-items-center rounded-xl bg-gradient-to-br from-[#e44358] to-red-pen font-hand text-2xl font-bold text-white shadow-md shadow-red-pen/30">
            S
          </span>
          <span className="hidden font-display text-xl font-extrabold tracking-tight sm:inline">Samjho</span>
        </Link>
        <div className="flex items-center gap-1 sm:gap-2">
          <StudentChip />
          <Link
            href="/practice"
            className="rounded-full px-2.5 py-2 text-sm font-semibold text-ink-soft hover:text-ink sm:px-3"
          >
            Practise
          </Link>
          <Link
            href="/progress"
            className="rounded-full px-2.5 py-2 text-sm font-semibold text-ink-soft hover:text-ink sm:px-3"
          >
            Progress
          </Link>
          <Link
            href="/check"
            className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white shadow-md shadow-ink/20 transition hover:-translate-y-px hover:bg-ink-soft"
          >
            Check a sum
          </Link>
        </div>
      </nav>
    </header>
  );
}
