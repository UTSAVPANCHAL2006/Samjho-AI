"use client";

// Samjho Lesson: everything after the red pen, as ONE guided lesson instead of separate cards.
//   with a mistake:   ① Galti samjho → ② Khud theek karo → ③ Poora solution → ④ Practice
//   answer unfinished:                ② Aage kaise badhein → ③ → ④
//   full marks:                                             ③ Exam mein aise likho → ④
// Every step can be opened any time. Jumping straight to the solution asks once, gently, to look at the mistake.

import { useEffect, useState } from "react";
import { api, ApiError, type Check, type CheckVisual, type Language, type NumberCheck, type Solution } from "@/lib/api";
import { readLanguage, saveLanguage } from "@/lib/student";
import { useVoice } from "@/lib/voice";
import { mistakeRemark } from "@/lib/mistakes";
import { PracticeCard } from "@/components/after-check";
import { ConceptVisual } from "@/components/concept-visual";
import { MathText, MixedMath } from "@/components/math";
import { SmartBoard, scenesFromSolution } from "@/components/smart-board";
import { Tutor } from "@/components/tutor";

type StepId = "understand" | "fix" | "solution" | "practice";
type Load<T> = { kind: "loading" } | { kind: "ready"; value: T } | { kind: "failed"; message: string };

interface StepInfo {
  id: StepId;
  title: string;
  hint: string;
}

function buildSteps(check: Check): StepInfo[] {
  const hasMistake = check.wrong_line !== null;
  const isFullMarks = check.score >= check.max_score;
  const steps: StepInfo[] = [];
  if (hasMistake) steps.push({ id: "understand", title: "Understand the mistake", hint: "See why, on the board" });
  if (!isFullMarks)
    steps.push({
      id: "fix",
      title: hasMistake ? "Fix it yourself" : "How to finish it",
      hint: "Talk it through with the tutor",
    });
  steps.push({
    id: "solution",
    title: isFullMarks ? "Write it like this in the exam" : "Full solution",
    hint: "Step by step, with voice",
  });
  steps.push({ id: "practice", title: "Practice", hint: "A new question from the same chapter" });
  return steps;
}

/** Loads once per key (e.g. per language); shows "loading" while the current key has no result yet. */
function useLoad<T>(load: () => Promise<T>, isWanted: boolean, key: string): Load<T> {
  const [result, setResult] = useState<{ key: string; load: Load<T> } | null>(null);
  useEffect(() => {
    if (!isWanted) return;
    let isCurrent = true;
    load()
      .then((value) => isCurrent && setResult({ key, load: { kind: "ready", value } }))
      .catch(
        (error: unknown) =>
          isCurrent &&
          setResult({
            key,
            load: { kind: "failed", message: error instanceof ApiError ? error.message : "Could not load this part." },
          }),
      );
    return () => {
      isCurrent = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload only when the key changes
  }, [isWanted, key]);
  return result && result.key === key ? result.load : { kind: "loading" };
}

/** The board arrives first with only the student's own line when the picture could not be drawn yet (a busy AI).
 *  Ask again twice in the background and swap in the full board when it is ready. */
function useCompleteVisual(first: Load<CheckVisual>, checkId: string, language: Language): Load<CheckVisual> {
  const [better, setBetter] = useState<{ key: string; value: CheckVisual } | null>(null);
  const isIncomplete = first.kind === "ready" && first.value.complete === false;
  useEffect(() => {
    if (!isIncomplete) return;
    let isCurrent = true;
    let tries = 0;
    let timer = 0;
    function retry() {
      tries += 1;
      api
        .getCheckVisual(checkId, language)
        .then((value) => {
          if (!isCurrent) return;
          if (value.complete !== false) setBetter({ key: `${checkId}-${language}`, value });
          else if (tries < 2) timer = window.setTimeout(retry, 6000);
        })
        .catch(() => undefined);
    }
    timer = window.setTimeout(retry, 4000);
    return () => {
      isCurrent = false;
      window.clearTimeout(timer);
    };
  }, [isIncomplete, checkId, language]);
  return better && better.key === `${checkId}-${language}` ? { kind: "ready", value: better.value } : first;
}

export function Lesson({ check, onFocusLine }: { check: Check; onFocusLine: (line: number) => void }) {
  const steps = buildSteps(check);
  const [language, setLanguage] = useState<Language>(readLanguage);
  const [active, setActive] = useState<StepId>(steps[0].id);
  const [visited, setVisited] = useState<Set<StepId>>(() => new Set([steps[0].id]));
  const [nudge, setNudge] = useState(false);
  const voice = useVoice();
  const hasMistake = check.wrong_line !== null;

  // Both start in the background as soon as the red pen is shown, so the lesson rarely waits.
  const firstVisual = useLoad<CheckVisual>(() => api.getCheckVisual(check.id, language), hasMistake, language);
  const visual = useCompleteVisual(firstVisual, check.id, language);
  const solution = useLoad<Solution>(() => api.getSolution(check.id, language), true, language);

  function open(step: StepId) {
    const skipsLearning = step === "solution" && hasMistake && !visited.has("understand") && !visited.has("fix");
    if (skipsLearning && !nudge) {
      setNudge(true);
      return;
    }
    voice.stopSpeaking();
    setNudge(false);
    setActive(step);
    setVisited((current) => new Set(current).add(step));
  }

  function chooseLanguage(option: Language) {
    setLanguage(option);
    saveLanguage(option);
  }

  const activeIndex = steps.findIndex((step) => step.id === active);
  const next = steps[activeIndex + 1];

  return (
    <section aria-label="Samjho lesson" className="lesson-sheet fade-up overflow-hidden">
      <header className="flex flex-wrap items-end justify-between gap-4 px-5 pt-6 sm:px-8">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-red-pen">Samjho lesson</p>
          <h2 className="mt-1 font-display text-[1.75rem] leading-tight text-ink sm:text-3xl">
            {hasMistake ? "Your mistake, step by step" : check.score >= check.max_score ? "Well done! Now the exam-ready way" : "Let's finish this together"}
          </h2>
        </div>
        <div role="radiogroup" aria-label="Lesson language" className="flex rounded-full bg-paper-deep p-1 text-sm">
          {(["hinglish", "en"] as const).map((option) => (
            <button
              key={option}
              role="radio"
              aria-checked={language === option}
              onClick={() => chooseLanguage(option)}
              className={`rounded-full px-3.5 py-1 font-semibold transition ${language === option ? "bg-card text-ink shadow-sm" : "text-muted hover:text-ink"}`}
            >
              {option === "en" ? "English" : "Hinglish"}
            </button>
          ))}
        </div>
      </header>

      <nav aria-label="Lesson steps" className="mt-5 overflow-x-auto px-5 sm:px-8">
        <ol className="flex min-w-max gap-2 border-b border-rule">
          {steps.map((step, index) => {
            const isActive = step.id === active;
            const isDone = visited.has(step.id) && !isActive;
            return (
              <li key={step.id}>
                <button
                  onClick={() => open(step.id)}
                  aria-current={isActive ? "step" : undefined}
                  className={`group relative flex items-center gap-2.5 px-3 pb-3 pt-1 text-left transition ${isActive ? "text-ink" : "text-muted hover:text-ink"}`}
                >
                  <span
                    className={`grid h-7 w-7 place-items-center rounded-full text-xs font-bold transition ${
                      isActive ? "bg-ink text-white" : isDone ? "bg-green-soft text-green-tick" : "bg-paper-deep text-muted"
                    }`}
                  >
                    {isDone ? "✓" : index + 1}
                  </span>
                  <span className="leading-tight">
                    <span className="block text-sm font-semibold">{step.title}</span>
                    <span className="block text-[11px] text-muted">{step.hint}</span>
                  </span>
                  <span
                    className={`absolute inset-x-2 -bottom-px h-[2px] rounded-full transition ${isActive ? "bg-red-pen" : "bg-transparent"}`}
                    aria-hidden
                  />
                </button>
              </li>
            );
          })}
        </ol>
      </nav>

      <div className="space-y-5 px-5 py-6 sm:px-8">
        {nudge ? (
          <div role="dialog" aria-label="Look at the mistake first?" className="fade-up rounded-2xl border border-rule bg-paper p-5">
            <p className="font-display text-lg text-ink">One minute — take 30 seconds to look at your mistake first?</p>
            <p className="mt-1 text-sm text-ink-soft">What you understand and fix yourself stays with you till the exam.</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                onClick={() => {
                  setNudge(false);
                  open("understand");
                }}
                className="rounded-full bg-ink px-5 py-2 text-sm font-semibold text-white"
              >
                Explain my mistake first
              </button>
              <button
                onClick={() => {
                  setVisited((current) => new Set(current).add("fix"));
                  setNudge(false);
                  voice.stopSpeaking();
                  setActive("solution");
                }}
                className="rounded-full px-5 py-2 text-sm font-semibold text-ink-soft ring-1 ring-rule hover:ring-ink-soft"
              >
                No, show the solution
              </button>
            </div>
          </div>
        ) : null}

        {active === "understand" ? (
          <UnderstandStep check={check} visual={visual} voice={voice} language={language} />
        ) : null}
        {active === "fix" ? (
          <Tutor key={`${check.id}-${language}`} checkId={check.id} language={language} onFocusLine={onFocusLine} />
        ) : null}
        {active === "solution" ? <SolutionStep solution={solution} voice={voice} language={language} /> : null}
        {active === "practice" ? <PracticeCard checkId={check.id} title="Next question from the same chapter" /> : null}

        {next ? (
          <div className="flex justify-end border-t border-rule pt-5">
            <button
              onClick={() => open(next.id)}
              className="inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold text-ink ring-1 ring-ink/15 transition hover:bg-ink hover:text-white"
            >
              Next: {next.title} <span aria-hidden>→</span>
            </button>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function UnderstandStep({
  check,
  visual,
  voice,
  language,
}: {
  check: Check;
  visual: Load<CheckVisual>;
  voice: ReturnType<typeof useVoice>;
  language: Language;
}) {
  const insight = visual.kind === "ready" ? visual.value.insight : null;
  const wrongLatex = check.wrong_line ? check.lines[check.wrong_line - 1]?.latex : null;
  return (
    <div className="space-y-5">
      {visual.kind === "ready" && visual.value.rightSoFar ? <RightSoFar right={visual.value.rightSoFar} /> : null}
      <figure className="teacher-note">
        <p className="font-hand text-[1.7rem] leading-none text-red-pen">{mistakeRemark(check.mistake)}</p>
        {wrongLatex ? (
          <p className="mt-3 overflow-x-auto text-lg text-ink">
            <span className="mr-2 text-xs font-semibold uppercase tracking-wide text-muted">Line {check.wrong_line}</span>
            <MathText latex={wrongLatex} />
          </p>
        ) : null}
        {insight ? (
          // The teacher's "why" leads (in the student's language); the maths proof sits under it, smaller.
          <>
            <p className="mt-4 max-w-2xl text-[1.05rem] leading-relaxed text-ink">
              <MixedMath text={insight} />
            </p>
            <figcaption className="mt-3 max-w-2xl border-t border-rule pt-3 text-sm leading-relaxed text-muted">
              <span className="mr-2 text-[11px] font-bold uppercase tracking-[0.12em] text-ink-soft">Maths proof</span>
              <MixedMath text={check.explanation ?? ""} />
            </figcaption>
          </>
        ) : (
          <figcaption className="mt-3 max-w-2xl leading-relaxed text-ink-soft">
            <MixedMath text={check.explanation ?? ""} />
          </figcaption>
        )}
      </figure>

      {visual.kind === "ready" && visual.value.numbers?.length ? <NumbersCard checks={visual.value.numbers} /> : null}

      {visual.kind === "loading" ? <BoardSkeleton label="The teacher is writing on the board…" /> : null}
      {visual.kind === "ready" && visual.value.visual ? (
        <ConceptVisual key={visual.value.visual.frames.length} visual={visual.value.visual} voice={voice} language={language} autoPlay />
      ) : null}
      {visual.kind === "ready" && visual.value.complete === false ? (
        <p className="text-sm text-muted">The board drawing is still being made — it will appear here as soon as it is ready.</p>
      ) : null}
      {visual.kind === "failed" || (visual.kind === "ready" && !visual.value.visual) ? (
        <p className="text-sm text-muted">We could not draw this one yet — the note above and the tutor (next step) will help.</p>
      ) : null}
    </div>
  );
}

/** A teacher starts with what is right, so the student knows what to keep. Only shown when something was proven right. */
function RightSoFar({ right }: { right: NonNullable<CheckVisual["rightSoFar"]> }) {
  const lastRight = right.lines.at(-1);
  if (!lastRight && !right.givens.length && !right.oneIdea) return null;
  return (
    <section aria-label="What you got right" className="rounded-2xl border border-green-tick/30 bg-paper p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-green-tick">What you got right</p>
      <ul className="mt-2 space-y-1.5 text-sm text-ink">
        {right.givens.length ? (
          <li>
            ✓ The question&apos;s values, written correctly:{" "}
            {right.givens.map((given, index) => (
              <span key={index} className="mr-2">
                <MathText latex={given} />
              </span>
            ))}
          </li>
        ) : null}
        {lastRight ? <li>✓ Every step up to line {lastRight.line} is correct — keep it.</li> : null}
        {right.oneIdea ? <li>✓ Your method is on the right track — only one idea went wrong.</li> : null}
      </ul>
    </section>
  );
}

const withApprox = (latex: string, approx?: string) => (approx ? `${latex} \\approx ${approx}` : latex);

function NumberTile({ label, latex, tone }: { label: string; latex: string; tone: "wrong" | "right" | "plain" }) {
  const color = tone === "wrong" ? "text-red-pen" : tone === "right" ? "text-green-tick" : "text-ink";
  return (
    <div className="min-w-0 flex-1 rounded-xl bg-card px-4 py-3 ring-1 ring-rule">
      <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-muted">{label}</p>
      <p className={`mt-1 overflow-x-auto text-lg ${color}`}>
        <MathText latex={latex} />
      </p>
    </div>
  );
}

/** The mistake measured: every number here was computed by the server's maths checker, never by the AI. */
function NumbersCard({ checks }: { checks: NumberCheck[] }) {
  return (
    <section aria-label="Check with numbers" className="rounded-2xl bg-paper p-5">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">Check with numbers</p>
      <div className="mt-3 space-y-4">
        {checks.map((check, index) => (
          <div key={index} className="space-y-2">
            {check.kind === "size" ? (
              <>
                <div className="flex flex-wrap gap-2">
                  <NumberTile label="Your answer" latex={withApprox(check.given, check.givenApprox)} tone="wrong" />
                  <NumberTile label="Right answer" latex={withApprox(check.expected, check.expectedApprox)} tone="right" />
                </div>
                {check.ratio ? (
                  <p className="text-sm text-ink-soft">
                    Yours is exactly <MathText latex={check.ratio} /> times the right answer — a clean factor like this
                    points to one wrong factor in the working.
                  </p>
                ) : null}
              </>
            ) : null}
            {check.kind === "plug_in" ? (
              <>
                <p className="text-sm text-ink-soft">
                  Put <MathText latex={`${check.variable} = ${check.given}`} /> back into{" "}
                  <MathText latex={check.equation} />:
                </p>
                <div className="flex flex-wrap gap-2">
                  <NumberTile label="Left side" latex={check.left} tone="plain" />
                  <NumberTile label="Right side" latex={check.right} tone="plain" />
                </div>
                <p className="text-sm font-semibold text-red-pen">
                  <MathText latex={`${check.left} \\neq ${check.right}`} /> — so this cannot be the answer.
                </p>
              </>
            ) : null}
            {check.kind === "test_point" ? (
              <>
                <p className="text-sm text-ink-soft">
                  Try <MathText latex={check.point} /> in both. A correct rewrite gives the same number for every value.
                </p>
                <div className="flex flex-wrap gap-2">
                  <NumberTile label="Question" latex={`${check.question} = ${check.questionValue}`} tone="right" />
                  <NumberTile label="Yours" latex={`${check.given} = ${check.givenValue}`} tone="wrong" />
                </div>
              </>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function SolutionStep({
  solution,
  voice,
  language,
}: {
  solution: Load<Solution>;
  voice: ReturnType<typeof useVoice>;
  language: Language;
}) {
  const [showText, setShowText] = useState(false);
  if (solution.kind === "loading") return <BoardSkeleton label="Writing the full solution…" />;
  if (solution.kind === "failed") return <p className="text-sm text-red-pen">{solution.message}</p>;
  const { steps, answer_latex: answer, verified } = solution.value;
  if (!steps.length) return <p className="text-sm text-muted">A checked solution for this question is not available yet.</p>;
  return (
    <div className="space-y-4">
      <SmartBoard
        scenes={scenesFromSolution(steps)}
        voice={voice}
        language={language}
        withVoice
        kicker={verified ? "Every line checked with maths" : "Solution"}
        title="Full solution"
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-ink-soft">
          Answer: <span className="text-lg text-ink"><MathText latex={answer} /></span>
        </p>
        <button onClick={() => setShowText(!showText)} className="text-sm font-semibold text-blue-ink underline-offset-4 hover:underline">
          {showText ? "Hide text" : "Read as text"}
        </button>
      </div>
      {showText ? (
        <ol className="space-y-3 rounded-2xl bg-paper p-5">
          {steps.map((step, index) => (
            <li key={index} className="flex gap-3">
              <span className="w-6 shrink-0 text-right font-display text-muted">{index + 1}.</span>
              <div className="min-w-0 space-y-1">
                {step.explain ? <p className="text-sm leading-relaxed text-ink-soft"><MixedMath text={step.explain} /></p> : null}
                {step.latex ? <div className="overflow-x-auto text-lg"><MathText latex={step.latex} /></div> : null}
              </div>
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}

function BoardSkeleton({ label }: { label: string }) {
  return (
    <div className="chalk-frame">
      <div className="chalkboard grid min-h-72 place-items-center">
        <p className="font-hand text-3xl text-chalk/50">{label}</p>
      </div>
    </div>
  );
}
