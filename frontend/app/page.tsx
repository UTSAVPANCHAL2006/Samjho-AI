// Home page: what Samjho does, why it is different, and one clear action ("Check my sum").

import Link from "next/link";
import { ArrowRightIcon, BookIcon, CameraIcon, ChatIcon, NotebookIcon, PenIcon, SigmaIcon, TargetIcon } from "@/components/icons";
import { MathText } from "@/components/math";
import { WelcomeBack } from "@/components/student";

const STEPS = [
  {
    icon: BookIcon,
    title: "Photo of the question",
    text: "Snap the question from any book — NCERT, RD Sharma, a worksheet. It is solved and checked by maths first.",
  },
  {
    icon: NotebookIcon,
    title: "Photo of your notebook",
    text: "Solve it on paper the way you always do, then one photo of the page. Every line is read.",
  },
  {
    icon: PenIcon,
    title: "Red pen + teacher",
    text: "See the exact line that went wrong, why, on a board with voice — then fix it yourself.",
  },
];

const DIFFERENCES = [
  {
    icon: TargetIcon,
    title: "Your mistake, not just the answer",
    text: "Answer apps show a perfect solution. Samjho reads YOUR working and finds the one line where it broke.",
  },
  {
    icon: SigmaIcon,
    title: "Marks checked by real maths",
    text: "Every line is compared with an answer key verified by a computer algebra system. Same working, same marks.",
  },
  {
    icon: ChatIcon,
    title: "A teacher that asks, not tells",
    text: "It asks about your line and gives hints in Hinglish or English. The full solution unlocks only after you try.",
  },
];

export default function HomePage() {
  return (
    <div className="space-y-24">
      <WelcomeBack />

      <section className="grid items-center gap-12 pt-4 md:grid-cols-[1.05fr_1fr]">
        <div className="space-y-7">
          <p className="inline-flex items-center gap-2 rounded-full bg-card px-3.5 py-1.5 text-xs font-semibold text-ink-soft shadow-sm ring-1 ring-rule">
            <span className="h-2 w-2 rounded-full bg-green-tick" aria-hidden /> CBSE Class 6–10 · Maths · Free
          </p>
          <h1 className="text-[2.9rem] font-extrabold leading-[1.02] sm:text-7xl">
            Spot the mistake.
            <br />
            <span className="relative inline-block">
              Understand
              <svg
                className="absolute -bottom-2 left-0 w-full"
                viewBox="0 0 200 12"
                preserveAspectRatio="none"
                aria-hidden
              >
                <path
                  d="M2 9 C 50 2, 120 2, 198 7"
                  stroke="var(--red-pen)"
                  strokeWidth="4"
                  fill="none"
                  strokeLinecap="round"
                />
              </svg>
            </span>{" "}
            it.
          </h1>
          <p className="max-w-lg text-lg leading-relaxed text-ink-soft">
            Two photos — the question and your notebook page. Samjho finds the exact line where it went wrong, then
            explains it like a teacher sitting next to you, in Hinglish or English.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Link href="/check" className="btn-primary px-7 py-4 text-base">
              <CameraIcon size={20} /> Check my sum
            </Link>
            <a href="#how" className="btn-secondary px-6 py-4">
              How it works
            </a>
          </div>
          <ul className="flex flex-wrap gap-x-5 gap-y-1.5 text-sm font-medium text-muted">
            <li>✓ Any chapter, any book</li>
            <li>✓ Just two photos</li>
            <li>✓ No login needed</li>
          </ul>
        </div>
        <DemoNotebook />
      </section>

      <section className="space-y-8">
        <div className="max-w-2xl space-y-3">
          <p className="eyebrow">Why Samjho</p>
          <h2 className="text-3xl font-extrabold sm:text-4xl">
            You don&apos;t learn from the answer. You learn from your mistake.
          </h2>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {DIFFERENCES.map((item) => (
            <article key={item.title} className="surface p-6 transition hover:-translate-y-0.5 sm:p-7">
              <span className="grid h-12 w-12 place-items-center rounded-2xl bg-red-soft text-red-pen" aria-hidden>
                <item.icon size={24} />
              </span>
              <h3 className="mt-4 text-lg font-bold">{item.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-soft">{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="how" className="scroll-mt-24 space-y-8">
        <div className="max-w-2xl space-y-3">
          <p className="eyebrow">How it works</p>
          <h2 className="text-3xl font-extrabold sm:text-4xl">Three steps. About a minute.</h2>
        </div>
        <ol className="grid gap-4 md:grid-cols-3">
          {STEPS.map((step, index) => (
            <li key={step.title} className="surface relative p-6 sm:p-7">
              <span className="flex items-center justify-between">
                <span className="grid h-12 w-12 place-items-center rounded-2xl bg-ink text-white" aria-hidden>
                  <step.icon size={24} />
                </span>
                <span className="font-hand text-5xl font-bold leading-none text-red-pen/80">{index + 1}</span>
              </span>
              <h3 className="mt-4 text-lg font-bold">{step.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-soft">{step.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="relative flex flex-col items-center gap-5 overflow-hidden rounded-[2.25rem] bg-ink px-6 py-16 text-center text-white shadow-2xl shadow-ink/30">
        <span
          className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-red-pen/25 blur-3xl"
          aria-hidden
        />
        <p className="relative font-hand text-4xl text-amber-soft">One sum a day.</p>
        <h2 className="relative max-w-xl text-3xl font-extrabold sm:text-4xl">
          Ten minutes of fixing your own mistakes beats an hour of reading solutions.
        </h2>
        <Link href="/check" className="btn-primary relative px-7 py-4">
          Check today&apos;s sum <ArrowRightIcon size={18} />
        </Link>
      </section>
    </div>
  );
}

function DemoNotebook() {
  const lines = [
    { latex: "x^2 - 5x + 6 = 0", mark: "✓", isWrong: false },
    { latex: "(x + 2)(x + 3) = 0", mark: "✗", isWrong: true },
    { latex: "x = -2,\\; x = -3", mark: "✗", isWrong: false },
  ];
  return (
    <figure
      className="relative mx-auto w-full max-w-md"
      aria-label="Example: Samjho checks a student's working and the tutor asks about the wrong line"
    >
      <div className="rotate-1 rounded-[1.75rem] border border-rule bg-card p-2.5 shadow-[var(--shadow-lift)]">
        <ol className="notebook-sheet rounded-2xl">
          {lines.map((line) => (
            <li
              key={line.latex}
              className={`flex min-h-14 items-center gap-3 py-2 pl-16 pr-5 ${line.isWrong ? "bg-red-soft/70" : ""}`}
            >
              <span
                className={`flex-1 text-lg ${line.isWrong ? "underline decoration-red-pen decoration-wavy decoration-2 underline-offset-8" : ""}`}
              >
                <MathText latex={line.latex} />
              </span>
              <span className={`font-hand text-4xl ${line.mark === "✓" ? "text-green-tick" : "text-red-pen"}`}>
                {line.mark}
              </span>
            </li>
          ))}
        </ol>
        <p className="px-4 pb-2 pt-3 text-right font-hand text-2xl text-red-pen">1 / 3</p>
      </div>
      <div className="-mt-4 ml-6 mr-2 space-y-2 sm:-ml-6">
        <div className="fade-up max-w-[90%] rounded-2xl rounded-bl-sm bg-ink px-4 py-3 text-sm leading-relaxed text-white shadow-lg">
          <span className="mb-1 block text-xs font-semibold text-white/60">Samjho teacher</span>
          Look at line 2 — multiply out <MathText latex="(x+2)(x+3)" />. What is the middle term?
        </div>
        <div className="fade-up ml-auto w-fit rounded-2xl rounded-br-sm bg-card px-4 py-2.5 text-sm shadow ring-1 ring-rule [animation-delay:400ms]">
          Oh, it is +5x… I got the sign wrong! 😅
        </div>
      </div>
    </figure>
  );
}
